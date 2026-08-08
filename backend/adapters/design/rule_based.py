"""
Rule-based Design/Theme Engine adapter — Technical Blueprint Section 3.4 / 6.

Deterministic, zero-cost, zero AI involvement, always. Applies a
layout/theme template to an outline to produce a complete Recipe.
Templates are data (a small dict here for Phase 1; a real
layout_templates/theme_sets table later per Blueprint Section 6 —
same interface, no change needed upstream when that happens).

Revision (ADR-022): also runs the per-slide layout classifier,
assigning each slide a layout_type (bullet_list, statistics,
comparison, process) that the Export adapter uses to render it.

Revision (ADR-024): theme selection now uses the document's actual
classified type (ADR-020) instead of audience_type.

Revision (ADR-025, Tier 2): sets a lightweight image_query hint on
the title slide and the first bullet_list content slide, derived from
their own title text. Deliberately just a short text string, not
actual image bytes — the Recipe/Outline stays lightweight and
regenerable (Constitution Principle 4), and the Export adapter fetches
the real image fresh at export time via the Media Port, same
"generate only when needed" discipline as everything else. Capped at
two slides per deck to respect Unsplash's free-tier rate limit
(50 requests/hour) rather than firing a request per slide.
"""

from backend.ports.design import DesignPort
from backend.models.recipe import Outline, Theme, Recipe
from backend.layout.layout_classifier import classify_layout

_KNOWN_THEMES = {
    "default": Theme(layout_template_id="standard", color_set_id="neutral", font_set_id="sans"),
    "academic": Theme(layout_template_id="standard", color_set_id="blue_academic", font_set_id="serif"),
}

_SERIF_DOCUMENT_TYPES = {"academic", "lecture"}
# Revision (ADR-027): raised from 2 to 4 per direct feedback that two
# images per deck felt sparse. Unsplash's free tier (50 requests/hour)
# is the real constraint — 4 images/deck supports roughly 12
# generations/hour across all users combined before hitting it, which
# is more than sufficient at the current pre-launch traffic level.
# Revisit this number (or move to the deferred multi-provider system)
# once real usage data shows it's actually being approached.
MAX_IMAGE_QUERIES_PER_DECK = 4


class RuleBasedDesignAdapter(DesignPort):
    def apply_theme(self, project_id: str, source_text: str, outline: Outline,
                     theme: Theme, audience_type: str, language: str) -> Recipe:
        if theme.layout_template_id != "default":
            resolved_theme = theme  # caller explicitly requested a theme — respect it
        else:
            theme_key = "academic" if outline.document_type in _SERIF_DOCUMENT_TYPES else "default"
            resolved_theme = _KNOWN_THEMES[theme_key]

        image_queries_assigned = 0
        for i, slide in enumerate(outline.slides):
            slide.layout_type = classify_layout(slide)
            is_title_slide = (i == 0)
            eligible = is_title_slide or slide.layout_type == "bullet_list"
            if eligible and image_queries_assigned < MAX_IMAGE_QUERIES_PER_DECK:
                slide.image_query = _derive_image_query(slide.title)
                image_queries_assigned += 1

        return Recipe.new(
            project_id=project_id,
            source_text=source_text,
            outline=outline,
            theme=resolved_theme,
            audience_type=audience_type,
            language=language,
        )


def _derive_image_query(title: str) -> str:
    """Turns a slide title into a reasonable image search query — the
    title itself is usually already a decent query, just trimmed of
    punctuation that wouldn't help a search API."""
    import re
    cleaned = re.sub(r"[^\w\s]", " ", title).strip()
    return cleaned or "presentation"
