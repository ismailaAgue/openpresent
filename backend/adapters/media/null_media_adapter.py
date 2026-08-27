"""
NullMediaAdapter — Phase 3.5 Tier 2 (ADR-025).

First-class "no images" implementation, same role as the AI Port's
NullAdapter: always available to select, always returns nothing,
$0 cost, no external dependency. This is the default — a deployment
with no image API key configured produces exactly the same decks as
before Tier 2 existed, just without images. Nothing breaks.
"""

from backend.ports.media import MediaPort


class NullMediaAdapter(MediaPort):
    def is_available(self) -> bool:
        return False

    def search_image(self, query: str, exclude_ids: set[str] | None = None):
        return None
