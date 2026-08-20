"""ImageResult — shared return type for every MediaPort provider adapter (ADR-029)."""

from dataclasses import dataclass


@dataclass
class ImageResult:
    image_bytes: bytes
    image_id: str          # provider-qualified, e.g. "unsplash:abc123" — used for dedup
    provider: str
    relevance_score: float  # 0.0-1.0, heuristic keyword-overlap score, see relevance.py
    attribution: str | None = None  # set when the provider's license requires visible credit
