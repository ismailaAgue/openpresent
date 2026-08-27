"""
Rule-based Design/Theme Engine adapter — Technical Blueprint Section 3.4/6.

Revision (ADR-030): this is now the DETERMINISTIC FALLBACK for layout
and image-query assignment, not the only path. When the AI pipeline
successfully ran its own layout-planning stage (ai_generate.py calls
AIPipelinePort.plan_layout before apply_theme), each slide already has
a real layout_type/image_query set, and apply_theme is told
(`ai_layout_planned=True`) to trust them as-is rather than
overwriting with the rule-based classifier. When AI planning is
unavailable or fails, or for the still-unchanged document-upload path,
this rule-based classifier remains the one running — same
Constitution guarantee as everywhere else in this codebase: AI is a
quality upgrade layered on top of a fully-functional deterministic
path, never a hard dependency.

Revision (ADR-030): the old MAX_IMAGE_QUERIES_PER_DECK=4 cap is gone.
That cap existed only because a single provider (Unsplash, 50 req/hr)
had no fallback if exhausted — a real constraint at the time. Now that
image quota/fallback is handled properly, per-provider, in the Media
layer (see backend/adapters/media/multi_provider_router.py:
QuotaTracker + provider fallback + graceful "no image" degradation),
an artificial deck-level cap is redundant and was capping decks well
below what the (now multi-provider, much higher combined) real quota
allows. Every eligible slide gets an image_query; whether it actually
gets an image depends on real provider availability at export time,
which is exactly where that decision belongs.
"""

from backend.ports.design import DesignPort
from backend.models.recipe import Outline, Theme, Recipe
from backend.layout.layout_classifier import classify_layout

_KNOWN_THEMES = {
    "default": Theme(layout_template_id="standard", color_set_id="neutral", font_set_id="sans"),
    "academic": Theme(layout_template_id="standard", color_set_id="blue_academic", font_set_id="serif"),
    # ADR-030 (presentation variety, spec Section 10): additional theme
    # variants so topic-first generation isn't visually identical every
    # time — see backend/pipeline/variety.py for selection logic.
    "warm": Theme(layout_template_id="standard", color_set_id="warm_editorial", font_set_id="sans"),
    "modern_dark": Theme(layout_template_id="standard", color_set_id="modern_dark", font_set_id="sans"),
}

_SERIF_DOCUMENT_TYPES = {"academic", "lecture"}
_IMAGE_ELIGIBLE_LAYOUTS = {"bullet_list"}


def get_theme_variant(variant_id: str) -> Theme:
    """Resolves a variety.THEME_VARIANT_IDS key ('default'/'academic'/
    'warm'/'modern_dark') to a fully-formed Theme — used by
    engines/ai_generate.py for presentation variety (spec Section 10).
    Returns the plain default Theme() for an unknown id rather than
    raising, since a bad/stale variant id should never be able to
    break generation."""
    return _KNOWN_THEMES.get(variant_id, Theme())


class RuleBasedDesignAdapter(DesignPort):
    def apply_theme(self, project_id: str, source_text: str, outline: Outline,
                     theme: Theme, audience_type: str, language: str,
                     ai_layout_planned: bool = False) -> Recipe:
        if theme.layout_template_id != "default":
            resolved_theme = theme  # caller explicitly requested a theme — respect it
        else:
            theme_key = "academic" if outline.document_type in _SERIF_DOCUMENT_TYPES else "default"
            resolved_theme = _KNOWN_THEMES[theme_key]

        if not ai_layout_planned:
            for i, slide in enumerate(outline.slides):
                slide.layout_type = classify_layout(slide)
                is_title_slide = (i == 0)
                eligible = is_title_slide or slide.layout_type in _IMAGE_ELIGIBLE_LAYOUTS
                if eligible:
                    slide.image_query = _derive_image_query(slide.title)
        # else: trust the AI-planned layout_type/image_query already on
        # each slide (set by AIPipelinePort.plan_layout before this call)

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
