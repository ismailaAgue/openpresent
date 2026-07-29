"""
Rule-based Design/Theme Engine adapter — Technical Blueprint Section 3.4 / 6.

Deterministic, zero-cost, zero AI involvement, always. Applies a
layout/theme template to an outline to produce a complete Recipe.
Templates are data (a small dict here for Phase 1; a real
layout_templates/theme_sets table later per Blueprint Section 6 —
same interface, no change needed upstream when that happens).
"""

from backend.ports.design import DesignPort
from backend.models.recipe import Outline, Theme, Recipe

_KNOWN_THEMES = {
    "default": Theme(layout_template_id="standard", color_set_id="neutral", font_set_id="sans"),
    "academic": Theme(layout_template_id="standard", color_set_id="blue_academic", font_set_id="serif"),
}


class RuleBasedDesignAdapter(DesignPort):
    def apply_theme(self, project_id: str, source_text: str, outline: Outline,
                     theme: Theme, audience_type: str, language: str) -> Recipe:
        resolved_theme = theme if theme.layout_template_id != "default" else _KNOWN_THEMES.get(
            "academic" if audience_type.startswith("student") else "default",
            _KNOWN_THEMES["default"],
        )
        return Recipe.new(
            project_id=project_id,
            source_text=source_text,
            outline=outline,
            theme=resolved_theme,
            audience_type=audience_type,
            language=language,
        )
