# backend/fuzzy_recall_matcher.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol
import re

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\b\d+\s*[\.\)]\s*", " ", s)
    s = re.sub(r"\b(net\s*wt|net\s*weight|wt)\b", " ", s)
    s = re.sub(r"\b(fl\s*oz|oz|lb|lbs|g|kg|ml|l|qt|pt|ct|count|pcs|pc)\b", " ", s)
    s = re.sub(r"\b\d+(\.\d+)?\b", " ", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


@dataclass
class RecallCandidate:
    id: int
    upc: str
    product_name: str
    brand_name: str
    recall_date: str
    reason: str
    severity: str

    source: str

    @property
    def display_text(self) -> str:
        return f"{self.brand_name} {self.product_name}".strip()

    @property
    def norm_text(self) -> str:
        return normalize_text(self.display_text)


@dataclass
class RecallMatch:
    candidate: RecallCandidate
    score: float
    algorithm: str


class RecallMatcher(Protocol):
    def best_match(self, query: str, threshold: float) -> Optional[RecallMatch]:
        ...


class BasicTokenSetRecallMatcher:
    """
    Simple baseline matcher:
    - normalize receipt text
    - compare against every recall candidate
    - use token_set_ratio
    - return the best candidate if above threshold
    """

    def __init__(self, candidates: List[RecallCandidate]):
        self.candidates = candidates

    def best_match(self, query: str, threshold: float = 0.78) -> Optional[RecallMatch]:
        q = normalize_text(query)
        if not q:
            return None

        best_candidate = None
        best_score = 0.0

        for c in self.candidates:
            cand_text = c.norm_text
            if not cand_text:
                continue

            score = fuzz.token_set_ratio(q, cand_text) / 100.0

            if score > best_score:
                best_score = score
                best_candidate = c

        if best_candidate is None or best_score < threshold:
            return None

        return RecallMatch(
            candidate=best_candidate,
            score=best_score,
            algorithm="basic_token_set",
        )


class TFIDFHybridRecallMatcher:
    """
    Production matcher:
      1) TF-IDF character n-gram retrieval
      2) RapidFuzz reranking on top-K candidates
    """

    def __init__(
        self,
        candidates: List[RecallCandidate],
        top_k: int = 25,
        w_char: float = 0.45,
        w_token: float = 0.35,
        w_partial: float = 0.20,
    ):
        self.candidates = candidates
        self.top_k = top_k
        self.w_char = w_char
        self.w_token = w_token
        self.w_partial = w_partial

        self.candidate_texts = [c.norm_text for c in candidates]

        if self.candidate_texts:
            self.vectorizer = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                min_df=1,
            )
            self.X_candidates = self.vectorizer.fit_transform(self.candidate_texts)
        else:
            self.vectorizer = None
            self.X_candidates = None

    def best_match(self, query: str, threshold: float = 0.60) -> Optional[RecallMatch]:
        q = normalize_text(query)
        if not q or not self.candidate_texts or self.vectorizer is None or self.X_candidates is None:
            return None

        X_q = self.vectorizer.transform([q])
        sim_char = cosine_similarity(X_q, self.X_candidates)[0]

        k = min(self.top_k, len(self.candidate_texts))
        if k == 0:
            return None

        idxs = np.argpartition(-sim_char, k - 1)[:k]

        token_scores = np.array([
            fuzz.token_set_ratio(q, self.candidate_texts[j]) / 100.0
            for j in idxs
        ])
        partial_scores = np.array([
            fuzz.partial_ratio(q, self.candidate_texts[j]) / 100.0
            for j in idxs
        ])
        char_scores = np.clip(sim_char[idxs], 0, 1)

        combined = (
            self.w_char * char_scores
            + self.w_token * token_scores
            + self.w_partial * partial_scores
        )

        best_local = int(np.argmax(combined))
        best_idx = int(idxs[best_local])
        best_score = float(combined[best_local])

        if best_score < threshold:
            return None

        return RecallMatch(
            candidate=self.candidates[best_idx],
            score=best_score,
            algorithm="tfidf_hybrid",
        )


def get_matcher(name: str, candidates: List[RecallCandidate]) -> RecallMatcher:
    name = (name or "tfidf_hybrid").lower()

    if name == "basic_token_set":
        return BasicTokenSetRecallMatcher(candidates)

    if name == "tfidf_hybrid":
        return TFIDFHybridRecallMatcher(candidates)

    raise ValueError(f"Unknown matcher: {name}")