"""
Design/Theme Engine Port — Technical Blueprint Section 3.4.

Responsibility: apply layout, typography, spacing, and theme to an
outline, producing a complete Recipe. Rule-based only, always — this
port intentionally has no AI-backed adapter (Constitution: design is a
solved, deterministic problem and should never be variable-cost or
variable-quality).
"""

from typing import Protocol
from backend.models.recipe import Outline, Theme, Recipe


class DesignPort(Protocol):
    def apply_theme(self, project_id: str, source_text: str, outline: Outline,
                     theme: Theme, audience_type: str, language: str,
                     ai_layout_planned: bool = False) -> Recipe:
        """Combine an outline and a theme into a complete, exportable
        Recipe. ai_layout_planned=True (ADR-030) tells the adapter that
        layout_type/image_query were already set upstream by an AI
        planning stage and should be trusted, not overwritten by the
        rule-based classifier — used by the topic-first pipeline when
        AI layout planning succeeded."""
        ...
