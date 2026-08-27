"""
PexelsProvider — ADR-029 (multi-provider image system, spec Section 9).

Pexels' free Search API. Requires a free API key (pexels.com/api) via
OPENPRESENT_PEXELS_API_KEY. Free tier: 200 requests/hour — no per-day
cap documented, generous relative to Unsplash, so this sits second in
the router's default priority (after Unsplash, which the product
already has a key for).
"""

from backend.adapters.media.provider_base import Candidate
from backend.adapters.media.quota import QuotaTracker
from backend.adapters.media.http_client import UrllibHttpClient, url_quote

SEARCH_URL = "https://api.pexels.com/v1/search"
REQUEST_TIMEOUT = 10
FREE_TIER_REQUESTS_PER_HOUR = 200


class PexelsProvider:
    name = "pexels"
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
                f"{SEARCH_URL}?query={url_quote(query)}&per_page={per_page}&orientation=landscape",
                headers={"Authorization": self.api_key},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.get("status_code") != 200:
                return []
            photos = (resp.get("json") or {}).get("photos") or []
            candidates = []
            for p in photos:
                url = (p.get("src") or {}).get("large") or (p.get("src") or {}).get("medium")
                if not url:
                    continue
                metadata = str(p.get("alt", "") or "")
                photographer = p.get("photographer")
                candidates.append(Candidate(
                    image_id=f"pexels:{p.get('id')}", provider=self.name,
                    fetch_url=url, metadata_text=metadata,
                    attribution=f"Photo by {photographer} on Pexels" if photographer else None,
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
