"""
UnsplashProvider — ADR-025, revised ADR-029 (multi-provider router).

Talks to Unsplash's free Search Photos API. Requires a free developer
access key (unsplash.com/developers) set via
OPENPRESENT_UNSPLASH_ACCESS_KEY. Free tier: 50 requests/hour — tracked
via QuotaTracker so the router can skip straight to the next provider
once exhausted, rather than firing requests that will just 403.

Verified against mocked HTTP responses in tests (no live network
access to api.unsplash.com in this sandbox) — real-world verification
happens on deployment, per the existing honest-limitation note this
codebase already carries for this adapter.
"""

from backend.adapters.media.provider_base import Candidate
from backend.adapters.media.quota import QuotaTracker
from backend.adapters.media.http_client import UrllibHttpClient, url_quote

SEARCH_URL = "https://api.unsplash.com/search/photos"
REQUEST_TIMEOUT = 10
FREE_TIER_REQUESTS_PER_HOUR = 50


class UnsplashProvider:
    name = "unsplash"
    requests_per_hour_limit = FREE_TIER_REQUESTS_PER_HOUR

    def __init__(self, access_key: str, http_client=None):
        self.access_key = access_key
        self._http = http_client or UrllibHttpClient()
        self._quota = QuotaTracker(FREE_TIER_REQUESTS_PER_HOUR)

    def is_available(self) -> bool:
        return bool(self.access_key) and self._quota.has_quota()

    def search_candidates(self, query: str, per_page: int = 5) -> list[Candidate]:
        if not self.access_key or not query:
            return []
        try:
            self._quota.record_request()
            resp = self._http.get(
                f"{SEARCH_URL}?query={url_quote(query)}&per_page={per_page}&orientation=landscape",
                headers={"Authorization": f"Client-ID {self.access_key}"},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.get("status_code") != 200:
                return []
            results = (resp.get("json") or {}).get("results") or []
            candidates = []
            for r in results:
                url = (r.get("urls") or {}).get("small")
                if not url:
                    continue
                metadata = " ".join(filter(None, [
                    r.get("description"), r.get("alt_description"),
                    " ".join(t.get("title", "") for t in (r.get("tags") or []) if isinstance(t, dict)),
                ]))
                candidates.append(Candidate(
                    image_id=f"unsplash:{r.get('id')}", provider=self.name,
                    fetch_url=url, metadata_text=metadata, attribution=None,
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
