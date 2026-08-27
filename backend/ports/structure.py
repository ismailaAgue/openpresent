"""
Structure Engine Port — Technical Blueprint Section 3.2.

Responsibility: convert extracted text into a slide-by-slide Outline.
The default adapter is rule-based and must be genuinely good on its own
(Constitution Principle 15) — AI only ever enhances this, never replaces
the requirement that this path works alone.
"""

from typing import Protocol
from backend.models.recipe import Outline


class StructurePort(Protocol):
    def build_outline(self, source_text: str, audience_type: str) -> Outline:
        """
        Build a slide-by-slide outline from source text.
        Must never raise for any non-empty text input — worst case,
        return a minimal single-slide outline. Empty/whitespace-only
        input should raise ValueError.
        """
        ...
