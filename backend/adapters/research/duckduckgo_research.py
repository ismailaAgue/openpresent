"""
DuckDuckGoResearchAdapter — ADR-030, spec Section 3 ("Research /
Knowledge Expansion (optional)").

Free, no API key required — scrapes DuckDuckGo's lite HTML results
page (lite.duckduckgo.com), which has a stable, simple structure with
no JS rendering required. This is honestly a best-effort, somewhat
fragile approach (HTML scraping is inherently more brittle than a
real search API, and is disabled by default — see registry.py) rather
than something to depend on for correctness. It's included because it
gives the Research stage a genuinely free, zero-setup option
consistent with the Infrastructure Cost Policy, with the explicit
tradeoff of being lower-reliability than a paid search API would be.

Enable via OPENPRESENT_RESEARCH_ADAPTER=duckduckgo (default: disabled,
NullResearchAdapter is used instead — see registry.get_research_adapter()).
Every failure mode (network error, changed page structure, empty
results) degrades to an empty ResearchBrief, never an exception that
could block generation.
"""

import re
from html import unescape
from backend.ports.research import ResearchPort
from backend.ports.ai_pipeline import ResearchBrief
from backend.adapters.media.http_client import UrllibHttpClient, url_quote

SEARCH_URL = "https://lite.duckduckgo.com/lite/"
REQUEST_TIMEOUT = 8
MAX_FACTS = 6

# DuckDuckGo lite's result snippets sit in <td class="result-snippet">...</td>
_SNIPPET_RE = re.compile(r'class="result-snippet">(.*?)</td>', re.DOTALL)


class DuckDuckGoResearchAdapter(ResearchPort):
    def __init__(self, http_client=None):
        self._http = http_client or UrllibHttpClient()

    def is_available(self) -> bool:
        return True  # no key needed — always configured when explicitly enabled

    def research(self, topic: str) -> ResearchBrief:
        if not topic or not topic.strip():
            return ResearchBrief()
        try:
            resp = self._http.get(
                f"{SEARCH_URL}?q={url_quote(topic)}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; OpenPresentResearch/1.0)"},
                timeout=REQUEST_TIMEOUT,
            )
            if resp.get("status_code") != 200:
                return ResearchBrief()
            html = resp.get("content", b"").decode("utf-8", errors="ignore")
            facts = self._extract_facts(html)
            return ResearchBrief(facts=facts, sources=["DuckDuckGo (best-effort, unverified)"] if facts else [])
        except Exception:
            return ResearchBrief()

    def _extract_facts(self, html: str) -> list[str]:
        raw_snippets = _SNIPPET_RE.findall(html)
        facts = []
        for raw in raw_snippets[:MAX_FACTS]:
            text = unescape(re.sub(r"<[^>]+>", "", raw)).strip()
            text = " ".join(text.split())
            if text and len(text) > 20:
                facts.append(text[:300])
        return facts
