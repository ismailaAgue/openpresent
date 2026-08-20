"""
Media Port — Phase 3.5 Tier 2 (ADR-025), revised ADR-029 (multi-provider).

ADR-029 changes the contract from "return raw bytes" to "return a
scored ImageResult with a stable id" — needed for the three
capabilities the product now requires: relevance scoring, duplicate
prevention across a deck, and provider routing/fallback. None of it
would be possible with a bare bytes return.

Images are still never permanently stored (Blueprint Section 3.7/9 —
"no large media database" principle) — providers are queried, and the
winning candidate's bytes fetched, fresh at export time. What IS now
cached (backend/adapters/media/relevance.py's in-process, in-memory
cache) is candidate *metadata* — id/description/score, not bytes —
and only for the lifetime of the running process, not persisted.

Same optional-capability discipline as the AI Port: every adapter must
degrade gracefully (return None) rather than raise when unavailable.
"""

from typing import Protocol
from backend.models.media import ImageResult


class MediaPort(Protocol):
    def is_available(self) -> bool:
        """Capacity/configuration check. Callers should check this
        before calling search_image, same pattern as AIPort."""
        ...

    def search_image(self, query: str, exclude_ids: set[str] | None = None) -> ImageResult | None:
        """Returns the best-scoring available image for the query, or
        None if unavailable, misconfigured, exhausted (quota), or the
        request failed for any reason — must never raise.

        exclude_ids: image_ids already used elsewhere in the same
        deck (duplicate prevention) — a matching candidate is skipped
        in favor of the next-best one, even if it search-ranks higher."""
        ...
