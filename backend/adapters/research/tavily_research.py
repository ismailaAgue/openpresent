"""
TavilyResearchAdapter — ADR-032.

Tavily (tavily.com) is a search API purpose-built for feeding LLM
pipelines, not a general web-search API repurposed for it — it returns
a synthesized answer plus source snippets specifically shaped for this
use case, which is a materially better fit for grounding the Strategy
stage than scraped search-result HTML ever was. Free tier available;
requires an API key (tavily.com -> sign up -> API key) via
TAVILY_API_KEY.

This is the top-priority research provider when configured (see
registry.get_research_adapter()) — ranked above Brave and Wikipedia
because both the content quality and the "already summarized for an
LLM" shape are the best match for what the Strategy stage needs.
"""

import json
import urllib.error
import urllib.request
from backend.ports.research import ResearchPort
from backend.ports.ai_pipeline import ResearchBrief
from backend.adapters.http_headers import with_user_agent

API_URL = "https://api.tavily.com/search"
REQUEST_TIMEOUT = 10
MAX_FACTS = 6


class TavilyResearchAdapter(ResearchPort):
    def __init__(self, api_key: str, http_post=None):
        self.api_key = api_key
        self._post = http_post or _post_json

    def is_available(self) -> bool:
        return bool(self.api_key)

    def research(self, topic: str) -> ResearchBrief:
        if not self.is_available() or not topic or not topic.strip():
            return ResearchBrief()
        try:
            body = {
                "api_key": self.api_key,
                "query": topic,
                "search_depth": "basic",
                "include_answer": True,
                "max_results": 5,
            }
            data = self._post(API_URL, body, REQUEST_TIMEOUT)

            facts: list[str] = []
            answer = (data.get("answer") or "").strip()
            if answer:
                facts.append(answer[:400])

            sources = []
            for r in (data.get("results") or []):
                content = (r.get("content") or "").strip()
                if content:
                    facts.append(content[:300])
                url = r.get("url")
                if url:
                    sources.append(url)
                if len(facts) >= MAX_FACTS:
                    break

            return ResearchBrief(facts=facts[:MAX_FACTS], sources=sources)
        except Exception:
            return ResearchBrief()


def _post_json(url: str, body: dict, timeout: float) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers=with_user_agent({"Content-Type": "application/json"})
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")
