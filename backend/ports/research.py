"""
Research Port — ADR-030/032, spec Section 3 ("Research / Knowledge
Expansion (optional)").

Optional by design, same as the spec's pipeline diagram marks it: the
Strategy stage (backend/adapters/ai/json_pipeline_base.py) works fine
with an empty ResearchBrief, just less grounded in current specifics.
Every adapter must degrade to "no facts" rather than block generation
— a slow or failed research call should never be the reason a deck
doesn't get made.

ADR-032: the concrete adapter wired up by default
(registry.get_research_adapter()) is now CompositeResearchAdapter,
which merges facts from multiple providers (Tavily/Brave when
configured, Wikipedia always) rather than relying on a single
best-effort HTML-scraping source — see composite_research.py for why
merging, not just failing over, is the right strategy here.
"""

from typing import Protocol
from backend.ports.ai_pipeline import ResearchBrief


class ResearchPort(Protocol):
    def is_available(self) -> bool:
        """Cheap configuration check — no network call."""
        ...

    def research(self, topic: str) -> ResearchBrief:
        """Never raises — returns an empty ResearchBrief on any
        failure. Callers should still wrap this in their own
        try/except as a second layer of protection (defense in depth,
        same pattern as every other optional-capability port here)."""
        ...
