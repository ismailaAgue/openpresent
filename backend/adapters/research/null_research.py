"""NullResearchAdapter — ADR-030. Same role as every other Null
adapter in this codebase: always available to select, always returns
an empty brief, $0 cost. The Research stage is skipped cleanly when
this is selected — Strategy generation proceeds without grounding
facts, which is a perfectly valid (if less current) starting point."""

from backend.ports.research import ResearchPort
from backend.ports.ai_pipeline import ResearchBrief


class NullResearchAdapter(ResearchPort):
    def is_available(self) -> bool:
        return False

    def research(self, topic: str) -> ResearchBrief:
        return ResearchBrief()
