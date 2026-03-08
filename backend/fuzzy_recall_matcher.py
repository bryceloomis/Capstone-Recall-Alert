from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol
import re

from rapidfuzz import fuzz


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
    firm_name: str
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


class OliviaBasicRecallMatcher:
    """
    Basic fuzzy matcher:
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
            algorithm="olivia_basic",
        )


def get_matcher(name: str, candidates: List[RecallCandidate]) -> RecallMatcher:
    name = (name or "olivia_basic").lower()

    if name == "olivia_basic":
        return OliviaBasicRecallMatcher(candidates)

    raise ValueError(f"Unknown matcher: {name}")