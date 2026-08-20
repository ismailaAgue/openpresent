"""
NullAdapter — Technical Blueprint Section 3.3, ADR-004.

This is a first-class adapter, not a fallback hack. It is what makes
"AI pauses, generation continues" (Constitution Principle 3) literally
true: every method is a safe pass-through / no-op, always available,
$0 cost.
"""

from backend.ports.ai import AIPort
from backend.models.recipe import Outline


class NullAdapter(AIPort):
    def is_available(self) -> bool:
        return False

    def propose_structure(self, outline: Outline, source_text: str,
                           target_slide_count: int | None = None) -> Outline:
        return outline  # unmodified — rule-based baseline stands as-is

    def rewrite(self, text: str, instructions: str = "") -> str:
        return text

    def translate(self, text: str, target_language: str) -> str:
        return text

    def summarize(self, text: str, max_length: int | None = None) -> str:
        if max_length is not None and len(text) > max_length:
            return text[:max_length - 1].rstrip() + "…"
        return text

    def suggest(self, context: str) -> list[str]:
        return []
