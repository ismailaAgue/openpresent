"""
WikimediaProvider — ADR-029. Wikimedia Commons' public search API —
no API key required at all, which makes it a genuinely free,
always-configurable last-resort fallback (useful if a deployment
never sets up any of the keyed providers). Images are freely licensed
but most require visible attribution — this adapter always sets
`attribution`, and the router/renderer are responsible for actually
displaying it (spec Section 8: "attribution handling where required").

No documented hard rate limit at this usage level, but a conservative
self-imposed quota is still applied (courtesy — Commons is a shared
public resource, not a commercial API meant for bulk automated use).
"""

import re
from backend.adapters.media.provider_base import Candidate
from backend.adapters.media.quota import QuotaTracker
from backend.adapters.media.http_client import UrllibHttpClient, url_quote

API_URL = "https://commons.wikimedia.org/w/api.php"
REQUEST_TIMEOUT = 10
SELF_IMPOSED_REQUESTS_PER_HOUR = 100


class WikimediaProvider:
    name = "wikimedia"
    requests_per_hour_limit = SELF_IMPOSED_REQUESTS_PER_HOUR

    def __init__(self, http_client=None):
        self._http = http_client or UrllibHttpClient()
        self._quota = QuotaTracker(SELF_IMPOSED_REQUESTS_PER_HOUR)

    def is_available(self) -> bool:
        return self._quota.has_quota()  # no API key needed — always configured

    def search_candidates(self, query: str, per_page: int = 5) -> list[Candidate]:
        if not query:
            return []
        try:
            self._quota.record_request()
            params = (
                f"?action=query&generator=search&gsrsearch={url_quote('filetype:bitmap ' + query)}"
                f"&gsrnamespace=6&gsrlimit={per_page}&prop=imageinfo"
                f"&iiprop=url|extmetadata&iiurlwidth=800&format=json"
            )
            resp = self._http.get(API_URL + params, timeout=REQUEST_TIMEOUT)
            if resp.get("status_code") != 200:
                return []
            pages = ((resp.get("json") or {}).get("query") or {}).get("pages") or {}
            candidates = []
            for page in pages.values():
                infos = page.get("imageinfo") or []
                if not infos:
                    continue
                info = infos[0]
                url = info.get("thumburl") or info.get("url")
                if not url:
                    continue
                meta = info.get("extmetadata") or {}
                description = _strip_html(meta.get("ImageDescription", {}).get("value", ""))
                categories = _strip_html(meta.get("Categories", {}).get("value", ""))
                artist = _strip_html(meta.get("Artist", {}).get("value", ""))
                license_name = meta.get("LicenseShortName", {}).get("value", "")
                title = page.get("title", "").replace("File:", "")
                candidates.append(Candidate(
                    image_id=f"wikimedia:{page.get('pageid')}", provider=self.name,
                    fetch_url=url, metadata_text=f"{title} {description} {categories}",
                    attribution=f"{title}" + (f" by {artist}" if artist else "")
                                + (f" ({license_name})" if license_name else "") + " — Wikimedia Commons",
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


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()
