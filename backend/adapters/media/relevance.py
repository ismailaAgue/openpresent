"""
Relevance scoring + candidate cache — ADR-029.

Two small, deliberately simple pieces shared by every provider adapter
and the router:

1. `score_relevance` — a free, offline heuristic (token-overlap between
   the search query and whatever text metadata a provider returns:
   description, alt text, tags). Not ML-based — there's no $0 way to
   run real image-relevance scoring without a paid vision API, and the
   Infrastructure Cost Policy rules that out for the MVP. This is
   honestly a coarse proxy, not a precision metric; documented as such
   rather than oversold. It's still strictly better than "take whatever
   the first search result is," which is what existed before.

2. `CandidateCache` — process-memory only (cleared on every restart/
   deploy), keyed by normalized query, storing scored candidate
   METADATA (id, description, score, provider) — never image bytes.
   This is what "caching" means here without violating the "no large
   media database" principle: repeated searches for the same query
   within a process's lifetime skip re-hitting provider APIs for
   candidate discovery, but the actual image bytes for the picked
   winner are still fetched fresh, every time, from the provider's URL.
"""

import re
import time
from dataclasses import dataclass, field

STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "for", "and", "or", "to", "with",
    "is", "are", "vs", "versus", "your", "this", "that", "at", "by",
}
CACHE_TTL_SECONDS = 3600  # candidate metadata cache lives 1 hour, then re-queried


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def score_relevance(query: str, *metadata_texts: str) -> float:
    """Jaccard-style overlap between query tokens and the union of all
    provided metadata text (description, alt text, tags, ...). 0.0 if
    there's no metadata to score against at all (still usable — the
    router treats a 0-score candidate as valid, just ranked lowest)."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    meta_tokens: set[str] = set()
    for t in metadata_texts:
        meta_tokens |= _tokenize(t)
    if not meta_tokens:
        return 0.0
    overlap = query_tokens & meta_tokens
    union = query_tokens | meta_tokens
    return round(len(overlap) / len(union), 3) if union else 0.0


@dataclass
class _CacheEntry:
    candidates: list  # list[dict] — provider-agnostic candidate metadata
    stored_at: float = field(default_factory=time.time)


class CandidateCache:
    def __init__(self, ttl_seconds: float = CACHE_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, _CacheEntry] = {}

    def get(self, query: str) -> list | None:
        entry = self._store.get(_normalize(query))
        if entry is None:
            return None
        if time.time() - entry.stored_at > self.ttl_seconds:
            del self._store[_normalize(query)]
            return None
        return entry.candidates

    def set(self, query: str, candidates: list) -> None:
        self._store[_normalize(query)] = _CacheEntry(candidates=candidates)

    def size(self) -> int:
        return len(self._store)


def _normalize(query: str) -> str:
    return " ".join((query or "").lower().split())
