"""
Internal provider-adapter shape — ADR-029.

Not MediaPort itself (that's the router's job — see
multi_provider_router.py). Each of Unsplash/Pexels/Pixabay/Wikimedia
implements this smaller two-phase interface instead: discover
candidates (cheap, metadata only) separately from fetching bytes
(only done once, for the single winning candidate, after scoring and
dedup — avoids downloading images for the N-1 candidates that don't
get used).
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Candidate:
    image_id: str          # provider-qualified, e.g. "pexels:123456"
    provider: str
    fetch_url: str          # where to download the actual image bytes from
    metadata_text: str = ""  # description/alt/tags — scored against the query
    attribution: str | None = None


class ImageProviderAdapter(Protocol):
    name: str
    requests_per_hour_limit: int

    def is_available(self) -> bool: ...

    def search_candidates(self, query: str, per_page: int = 5) -> list[Candidate]:
        """Returns up to per_page candidates, or [] on any failure —
        never raises."""
        ...

    def fetch_bytes(self, candidate: Candidate) -> bytes | None:
        """Downloads the actual image for one candidate. Never raises —
        returns None on any failure."""
        ...
