"""
CompositeResearchAdapter — ADR-032.

Deliberately different merge strategy from CompositeAIAdapter (which
cascades — tries provider A, falls to B ONLY on failure, uses exactly
one result) and from MultiProviderMediaAdapter (which discovers
candidates from multiple providers but embeds exactly one winning
image per slide). Here, the goal isn't "the first one that works" —
it's "the best combined grounding for the Strategy stage," so this
adapter queries multiple available providers and MERGES their facts
(deduplicated, capped) rather than stopping at the first success. A
Tavily result and a Wikipedia result about the same topic are
genuinely complementary — one is current-web, the other is
encyclopedic-authoritative — and combining them produces a richer
ResearchBrief than either alone.

Priority/inclusion order (registry.get_research_adapter() wires this
up): Tavily (if configured) -> Brave (if configured) -> Wikipedia
(always available, no key) -> DuckDuckGo (only if explicitly opted
into via OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH=true — kept available
as a free bonus source, but no longer the default/primary free option
now that Wikipedia's real REST API covers that role more reliably).

Bounded by MAX_PROVIDERS_QUERIED and MAX_TOTAL_FACTS so this doesn't
uncontrollably add latency to every generation — research already runs
before the (already multi-call) AI pipeline, so it has its own budget.
"""

from backend.ports.research import ResearchPort
from backend.ports.ai_pipeline import ResearchBrief
from backend.monitoring.sentry_setup import capture_exception, add_breadcrumb

MAX_PROVIDERS_QUERIED = 3
MAX_TOTAL_FACTS = 10


class CompositeResearchAdapter(ResearchPort):
    def __init__(self, providers: list):
        # providers: ordered list of ResearchPort-shaped objects,
        # highest-quality/most-current first. Unavailable (unconfigured)
        # ones are skipped automatically.
        self.providers = providers

    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)

    def research(self, topic: str) -> ResearchBrief:
        if not topic or not topic.strip():
            return ResearchBrief()

        merged_facts: list[str] = []
        merged_sources: list[str] = []
        seen_normalized: set[str] = set()
        queried = 0

        for provider in self.providers:
            if queried >= MAX_PROVIDERS_QUERIED or len(merged_facts) >= MAX_TOTAL_FACTS:
                break
            if not provider.is_available():
                continue
            queried += 1
            try:
                brief = provider.research(topic)
            except Exception as e:
                capture_exception(e, tags={"stage": "research", "provider": type(provider).__name__})
                continue

            added = 0
            for fact in brief.facts:
                key = " ".join(fact.lower().split())
                if key and key not in seen_normalized:
                    seen_normalized.add(key)
                    merged_facts.append(fact)
                    added += 1
                    if len(merged_facts) >= MAX_TOTAL_FACTS:
                        break
            merged_sources.extend(brief.sources)
            add_breadcrumb("research", f"{type(provider).__name__} contributed facts",
                            data={"facts_added": added})

        return ResearchBrief(facts=merged_facts, sources=merged_sources)
