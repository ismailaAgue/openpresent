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
                     theme: Theme, audience_type: str, language: str) -> Recipe:
        """Combine an outline and a theme into a complete, exportable Recipe."""
        ...
