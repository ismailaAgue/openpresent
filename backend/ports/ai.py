"""
AI Port — Technical Blueprint Section 3.3 / Section 10, ADR-008.

Capability-scoped, not one generic "call AI" method — each capability
degrades independently. Every method must have a well-defined,
inexpensive no-op behavior (see adapters/ai/null_adapter.py), which
is what makes "AI pauses, generation continues" (Constitution
Principle 3) an enforced behavior rather than a hope.

Phase 1 wires this port to NullAdapter only — no AI cost, no AI
dependency, by construction. Phase 2 adds LocalModelAdapter.
"""

from typing import Protocol
from backend.models.recipe import Outline


class AIPort(Protocol):
    def is_available(self) -> bool:
        """
        Capacity check. Must be called before any other method by
        callers that want to respect the AI-optional guarantee —
        engines should check this and skip straight to the rule-based
        result if False, rather than calling and catching an error.
        """
        ...

    def propose_structure(self, outline: Outline, source_text: str,
                           target_slide_count: int | None = None) -> Outline:
        """Given a rule-based baseline outline, propose an improved one.
        Must return the input unmodified if AI is unavailable — never
        raise. target_slide_count (ADR-034) is an optional hint: when
        given, try to consolidate/expand the outline toward roughly
        that many slides. Adapters that don't support this hint should
        simply ignore it — never raise or refuse enhancement just
        because it was passed."""
        ...

    def rewrite(self, text: str, instructions: str = "") -> str:
        ...

    def translate(self, text: str, target_language: str) -> str:
        ...

    def summarize(self, text: str, max_length: int | None = None) -> str:
        ...

    def suggest(self, context: str) -> list[str]:
        ...
