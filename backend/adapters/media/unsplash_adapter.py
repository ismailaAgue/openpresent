"""
UnsplashMediaAdapter — Phase 3.5 Tier 2 (ADR-025).

Talks to Unsplash's free Search Photos API. Requires a free developer
access key (unsplash.com/developers) set via OPENPRESENT_UNSPLASH_ACCESS_KEY.
Not AI generation — real, existing, freely-licensed photographs, so
this doesn't touch the Constitution's "no paid AI dependency" principle
at all; it's a genuinely different kind of external dependency (a
content retrieval API, not a generation API), and it's free at the
tier this project needs.

Same capacity-check-and-never-raise discipline as LocalModelAdapter:
every method degrades to "no image" rather than breaking generation,
and the HTTP client is injectable so this adapter's logic is fully
testable without a real network call or a real API key (see
tests/contract/test_media_port.py) — the same pattern already proven
out for the AI Port in Phase 2.

Honest limitation, stated plainly: this sandbox has no network access
to api.unsplash.com, so this adapter is verified correct against
mocked HTTP responses, not against the real live API. That real-world
verification happens on first live deployment with a real access key —
see the companion setup guide.
"""

import json as _json
from backend.ports.media import MediaPort

SEARCH_URL = "https://api.unsplash.com/search/photos"
HEALTH_CHECK_TIMEOUT = 3
REQUEST_TIMEOUT = 10

# Unsplash's free "Demo" tier allows 50 requests/hour — genuinely
# restrictive at any real scale. This is a known, documented
# constraint (see ADR-025), not an oversight; fine for a quiet launch,
# a real bottleneck if traffic grows, at which point either a paid
# Unsplash tier or a caching layer becomes necessary.


class UnsplashMediaAdapter(MediaPort):
    def __init__(self, access_key: str, http_client=None):
        self.access_key = access_key
        self._http = http_client or _UrllibHttpClient()

    def is_available(self) -> bool:
        return bool(self.access_key)

    def search_image(self, query: str) -> bytes | None:
        if not self.access_key or not query:
            return None
        try:
            search_resp = self._http.get(
                f"{SEARCH_URL}?query={_url_quote(query)}&per_page=1&orientation=landscape",
                headers={"Authorization": f"Client-ID {self.access_key}"},
                timeout=REQUEST_TIMEOUT,
            )
            if search_resp.get("status_code") != 200:
                return None
            data = search_resp.get("json") or {}
            results = data.get("results") or []
            if not results:
                return None
            image_url = results[0].get("urls", {}).get("small")
            if not image_url:
                return None

            image_resp = self._http.get(image_url, timeout=REQUEST_TIMEOUT)
            if image_resp.get("status_code") != 200:
                return None
            return image_resp.get("content")
        except Exception:
            return None  # never raise — degrade to "no image," never break generation


def _url_quote(s: str) -> str:
    import urllib.parse
    return urllib.parse.quote(s)


class _UrllibHttpClient:
    """Real HTTP client using only the standard library — no new
    dependency needed, same choice as LocalModelAdapter's client."""

    def get(self, url: str, headers: dict | None = None, timeout: float = 10) -> dict:
        import urllib.request
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            parsed_json = None
            if "application/json" in content_type:
                try:
                    parsed_json = _json.loads(content)
                except Exception:
                    parsed_json = None
            return {"status_code": resp.status, "content": content, "json": parsed_json}
