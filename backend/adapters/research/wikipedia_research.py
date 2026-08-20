"""
WikipediaResearchAdapter — ADR-032.

Free, no API key required — the Research-stage equivalent of
WikimediaProvider for images: a genuinely reliable, always-configured
universal fallback, not a scraping workaround. Uses Wikipedia's real,
documented, stable REST API (not HTML scraping), which is why it
replaces DuckDuckGo HTML-scraping as the default no-key option rather
than sitting alongside it as another best-effort source.

Two real API calls, both documented and stable:
1. MediaWiki search API — finds the best-matching article title.
2. Wikipedia REST summary API — a clean, well-formed 1-3 sentence
   factual extract for that article, plus its canonical URL.

Trade-off, stated plainly: Wikipedia is encyclopedic and authoritative
but not current-events-fast — a topic from the last few days may not
have an article yet, or may be thin. That's exactly why it's the
*fallback* tier in the composite (registry.get_research_adapter()),
not the primary one when a real search API (Tavily/Brave) is
configured.
"""

import re
from backend.ports.research import ResearchPort
from backend.ports.ai_pipeline import ResearchBrief
from backend.adapters.media.http_client import UrllibHttpClient, url_quote

SEARCH_URL = "https://en.wikipedia.org/w/api.php"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
REQUEST_TIMEOUT = 8
MAX_FACTS = 4


class WikipediaResearchAdapter(ResearchPort):
    def __init__(self, http_client=None):
        self._http = http_client or UrllibHttpClient()

    def is_available(self) -> bool:
        return True  # no key needed — always configured

    def research(self, topic: str) -> ResearchBrief:
        if not topic or not topic.strip():
            return ResearchBrief()
        try:
            title = self._find_best_article(topic)
            if not title:
                return ResearchBrief()
            return self._fetch_summary(title)
        except Exception:
            return ResearchBrief()

    def _find_best_article(self, topic: str) -> str | None:
        params = f"?action=query&list=search&srsearch={url_quote(topic)}&srlimit=1&format=json"
        resp = self._http.get(SEARCH_URL + params, timeout=REQUEST_TIMEOUT)
        if resp.get("status_code") != 200:
            return None
        results = ((resp.get("json") or {}).get("query") or {}).get("search") or []
        return results[0]["title"] if results else None

    def _fetch_summary(self, title: str) -> ResearchBrief:
        resp = self._http.get(SUMMARY_URL + url_quote(title), timeout=REQUEST_TIMEOUT)
        if resp.get("status_code") != 200:
            return ResearchBrief()
        data = resp.get("json") or {}
        extract = (data.get("extract") or "").strip()
        if not extract:
            return ResearchBrief()

        # Split the extract into individual sentence-level facts rather
        # than one large blob — matches the granularity of the other
        # providers' fact lists and keeps the Strategy prompt's
        # "grounding facts" list scannable.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", extract) if s.strip()]
        facts = sentences[:MAX_FACTS]

        page_url = ((data.get("content_urls") or {}).get("desktop") or {}).get("page")
        sources = [page_url] if page_url else []

        return ResearchBrief(facts=facts, sources=sources)
