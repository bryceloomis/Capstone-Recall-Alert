# backend/fuzzy_recall_matcher.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol
import re

import numpy as np
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.special import expit


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


def calc_cosine_similarity(receipt_item_vec, recalls_vec):
    cosine_similarity_index = []
    n = 0

    for r in recalls_vec:
        cosine_similarity_index.append([cosine_similarity(receipt_item_vec, r)[0][0], n])
        n = n + 1
        
    cosine_similarity_index = sorted(cosine_similarity_index, reverse = True)
    return cosine_similarity_index[0][0], cosine_similarity_index [0][1]

def calc_fuzz_similarity(receipt_item, recalls, fuzz_type):
    fuzz_similarity_index = []
    n = 0

    for r in recalls:
        if fuzz_type == 'partial':
            fuzz_similarity_index.append([fuzz.partial_ratio(receipt_item, r)/100, n])
        elif fuzz_type == 'token_set':
            fuzz_similarity_index.append([fuzz.token_set_ratio(receipt_item, r)/100, n])
        else:
            fuzz_similarity_index.append(0)
        n = n+1
    
    fuzz_similarity_index = sorted(fuzz_similarity_index, reverse = True)
    return fuzz_similarity_index[0][0], fuzz_similarity_index[0][1]

def calc_ce_similarity(receipt_item, recalls, ce):
    ce_similarity_index = []
    n = 0

    for r in recalls:
        pair = [receipt_item, r]
        r_logit = (ce.predict(pair, batch_size = 64, show_progress_bar=False))
        ce_similarity_index.append([expit(r_logit), n])
        n = n+1
        
    ce_similarity_index = sorted(ce_similarity_index, reverse = True)
    return ce_similarity_index[0][0], ce_similarity_index[0][1]

def word_by_word_similarity(receipt, recall):
  receipt_words = receipt.lower().split(" ")
  recall_words = recall.lower().split(" ")

  max_receiptword_recallword = []

  for x in receipt_words:
    if len(x) > 2:
      max_similarity = 0
      for y in recall_words:
        if len(y) > 2:
          similarity = fuzz.partial_ratio(x, y)/100
          if similarity > max_similarity:
            max_similarity = similarity

      max_receiptword_recallword.append(max_similarity)

  if (all(c > 0.55 for c in max_receiptword_recallword)) & ((sum(max_receiptword_recallword)/len(max_receiptword_recallword)) > 0.8):
    return True
  else:
    return False

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


class EnsembleMatcher:
    """
    Ensemble matcher: waterfall method using best of four similarity measures
    plus similarity on word-by-word basis
    """
    def __init__(
        self,
        candidates: List[RecallCandidate],
        cutoff: int = 2,
        mean_partial: float = 0.2245,
        stdev_partial: float = 0.0615,
        mean_tokenset: float = 0.1540,
        stdev_tokenset: float = 0.05126,
        mean_ce: float = 0.1751,
        stdev_ce: float = 0.3556,
        mean_tfidf: float = 0.3781,
        stdev_tfidf: float = 0.2234,
    ):
        self.candidates = candidates
        self.cutoff = cutoff
        self.mean_partial = mean_partial
        self.stdev_partial = stdev_partial
        self.mean_tokenset = mean_tokenset
        self.mean_ce = mean_ce
        self.stdev_ce = stdev_ce
        self.mean_tfidf = mean_tfidf
        self.stdev_tfidf = stdev_tfidf

        self.candidate_texts = [c for c in candidates]

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

    def best_match(self, query: str) -> Optional[RecallMatch]:
        from sentence_transformers import CrossEncoder
        CE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ce = CrossEncoder(CE_MODEL)

        q = normalize_text(query)
        if not q or not self.candidate_texts or self.vectorizer is None or self.X_candidates is None:
            return None

        #rapidfuzz partial
        similarity_partial, idx_partial = calc_fuzz_similarity(q, self.candidates_texts, "partial")
        z_partial = (similarity_partial - self.mean_partial)/self.stdev_partial

        #rapidfuzz tokenset
        similarity_tokenset, idx_tokenset = calc_fuzz_similarity(q, self.candidates_texts, "token_set")
        z_tokenset = (similarity_tokenset - self.mean_tokenset)/self.stdev_tokenset

        #cross-encoder
        similarity_ce, idx_ce = calc_ce_similarity(q, self.candidates_texts, ce)
        z_ce = (similarity_ce - self.mean_ce)/self.stdev_ce

        #tfidf
        similarity_tfidf, idx_tfidf = calc_cosine_similarity(X_q, self.X_candidates)
        z_tfidf = (similarity_tfidf - self.mean_tfidf)/self.stdev_tfidf


        #sort similarity measures from best to worst
        for_sort = [[z_partial, similarity_partial, idx_partial, cutoff],
                    [z_tokenset, similarity_tokenset, idx_tokenset, cutoff],
                    [z_ce, similarity_ce, idx_ce, cutoff],
                    [ze_tfdif, similarity_tfidf, idx_tfidf, cutoff]]
        for_sort = sorted(for_sort, reverse = True)

        ensemble_similarity = ''
        ensemble_index = ''

        #use the similarity match for the best measure if it crosses the threshold AND
        #word-by-word similarity also crosses threshold
        #if not, move to next similarity measure and test again
        if for_sort[0][0] >= for_sort[0][3]:
            if word_by_word_similarity(receipt_item, recalls[for_sort[0][2]]):
                ensemble_similarity = for_sort[0][1]
                ensemble_index = for_sort[0][2]
                
        elif for_sort[1][0] >= for_sort[1][3]:
            if word_by_word_similarity(receipt_item, recalls[for_sort[1][2]]):
                ensemble_similarity = for_sort[1][1]
                ensemble_index = for_sort[1][2]
        
        elif for_sort[2][0] >= for_sort[2][3]:
            if word_by_word_similarity(receipt_item, recalls[for_sort[2][2]]):
                ensemble_similarity = for_sort[2][1]
                ensemble_index = for_sort[2][2]
        
        elif for_sort[3][0] >= for_sort[3][3]:
            if word_by_word_similarity(receipt_item, recalls[for_sort[3][2]]):
                ensemble_similarity = for_sort[3][1]
                ensemble_index = for_sort[3][2]

        best_idx = ensemble_index
        if ensemble_similarity == '':
            best_score = 0
        else:
            best_score = ensemble_similarity

        if best_idx == '':
            return None

        return RecallMatch(
            candidate=self.candidates[best_idx],
            score=best_score,
            algorithm="ensemble",
        )


def get_matcher(name: str, candidates: List[RecallCandidate]) -> RecallMatcher:
    name = (name or "tfidf_hybrid").lower()

    if name == "basic_token_set":
        return BasicTokenSetRecallMatcher(candidates)

    if name == "tfidf_hybrid":
        return TFIDFHybridRecallMatcher(candidates)

    if name == 'ensemble':
        return EnsembleMatcher(candidates)

    raise ValueError(f"Unknown matcher: {name}")