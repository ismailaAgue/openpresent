"""
BraveSearchResearchAdapter — ADR-032.

Brave Search's independent index (not repackaged Google/Bing results)
via its API, with a genuine free tier. Requires an API key
(brave.com/search/api -> sign up) via BRAVE_SEARCH_API_KEY. Ranked
below Tavily (which is purpose-shaped for LLM grounding) but above
Wikipedia for currency — Brave indexes the live web, Wikipedia is
encyclopedic and slower to reflect very recent events.

Free-tier request limits change over time — verify current limits at
brave.com/search/api before assuming capacity, same caveat given for
every other free-tier provider in this codebase.
"""

from backend.ports.research import ResearchPort
from backend.ports.ai_pipeline import ResearchBrief
from backend.adapters.media.http_client import UrllibHttpClient, url_quote
import re

API_URL = "https://api.search.brave.com/res/v1/web/search"
REQUEST_TIMEOUT = 10
MAX_FACTS = 6


class BraveSearchResearchAdapter(ResearchPort):
    def __init__(self, api_key: str, http_client=None):
        self.api_key = api_key
        self._http = http_client or UrllibHttpClient()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def research(self, topic: str) -> ResearchBrief:
        if not self.is_available() or not topic or not topic.strip():
            return ResearchBrief()
        try:
            resp = self._http.get(
                f"{API_URL}?q={url_quote(topic)}&count=5",
                headers={"Accept": "application/json", "X-Subscription-Token": self.api_key},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.get("status_code") != 200:
                return ResearchBrief()

            results = ((resp.get("json") or {}).get("web") or {}).get("results") or []
            facts, sources = [], []
            for r in results:
                description = _strip_tags(r.get("description", ""))
                if description:
                    facts.append(description[:300])
                url = r.get("url")
                if url:
                    sources.append(url)
                if len(facts) >= MAX_FACTS:
                    break

            return ResearchBrief(facts=facts, sources=sources)
        except Exception:
            return ResearchBrief()


def _strip_tags(text: str) -> str:
    # Brave sometimes wraps matched terms in <strong> — strip any markup.
    return re.sub(r"<[^>]+>", "", text or "").strip()
