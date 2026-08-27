"""
PixabayProvider — ADR-029. Pixabay's free Search API. Requires a free
API key (pixabay.com/api/docs) via OPENPRESENT_PIXABAY_API_KEY. Free
tier: 5,000 requests/hour (Pixabay's most generous limit of the four
providers) — a good last-resort fallback once Unsplash/Pexels are
exhausted or unconfigured.
"""

from backend.adapters.media.provider_base import Candidate
from backend.adapters.media.quota import QuotaTracker
from backend.adapters.media.http_client import UrllibHttpClient, url_quote

SEARCH_URL = "https://pixabay.com/api/"
REQUEST_TIMEOUT = 10
FREE_TIER_REQUESTS_PER_HOUR = 5000


class PixabayProvider:
    name = "pixabay"
    requests_per_hour_limit = FREE_TIER_REQUESTS_PER_HOUR

    def __init__(self, api_key: str, http_client=None):
        self.api_key = api_key
        self._http = http_client or UrllibHttpClient()
        self._quota = QuotaTracker(FREE_TIER_REQUESTS_PER_HOUR)

    def is_available(self) -> bool:
        return bool(self.api_key) and self._quota.has_quota()

    def search_candidates(self, query: str, per_page: int = 5) -> list[Candidate]:
        if not self.api_key or not query:
            return []
        try:
            self._quota.record_request()
            resp = self._http.get(
                f"{SEARCH_URL}?key={self.api_key}&q={url_quote(query)}"
                f"&image_type=photo&orientation=horizontal&per_page={max(per_page, 3)}",
                timeout=REQUEST_TIMEOUT,
            )
            if resp.get("status_code") != 200:
                return []
            hits = (resp.get("json") or {}).get("hits") or []
            candidates = []
            for h in hits[:per_page]:
                url = h.get("largeImageURL") or h.get("webformatURL")
                if not url:
                    continue
                metadata = str(h.get("tags", "") or "")
                user = h.get("user")
                candidates.append(Candidate(
                    image_id=f"pixabay:{h.get('id')}", provider=self.name,
                    fetch_url=url, metadata_text=metadata,
                    attribution=f"Image by {user} on Pixabay" if user else None,
                ))
            return candidates
        except Exception:
            return []

    def fetch_bytes(self, candidate: Candidate) -> bytes | None:
        try:
            resp = self._http.get(candidate.fetch_url, timeout=REQUEST_TIMEOUT)
            if resp.get("status_code") != 200:
                return None
            return resp.get("content")
        except Exception:
            return None
