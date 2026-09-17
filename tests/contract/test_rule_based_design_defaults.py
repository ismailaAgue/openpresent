"""
RuleBasedDesignAdapter's default-theme resolution — ADR-071, ADR-073.

No prior test file covered apply_theme()'s own theme_key resolution
directly (test_ai_generate_engine.py covers the topic-first pipeline's
separate variety.pick_theme_variant() path, a different mechanism).
ADR-071 made editorial_cream the default with one exception (academic/
lecture document types kept blue_academic); ADR-073 removed that
exception too — "editorial cream only" is now unconditional here,
document_type no longer affects theme resolution at all.
"""

from backend.adapters.design.rule_based import RuleBasedDesignAdapter, _KNOWN_THEMES
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource, Theme


def make_outline(document_type: str = "general") -> Outline:
    return Outline(
        structure_source=StructureSource.RULE_BASED,
        document_type=document_type,
        slides=[
            Slide(order=1, title="Cover", content_blocks=[]),
            Slide(order=2, title="Details", content_blocks=[
                ContentBlock(type=BlockType.BULLET, text="Some point."),
            ]),
        ],
    )


def test_no_explicit_theme_resolves_to_editorial_cream():
    outline = make_outline(document_type="general")
    recipe = RuleBasedDesignAdapter().apply_theme(
        project_id="p1", source_text="doc text", outline=outline,
        theme=Theme(),  # layout_template_id="default" — nothing explicitly requested
        audience_type="general", language="en",
    )
    assert recipe.theme.color_set_id == "editorial_cream"


def test_academic_and_lecture_document_types_also_get_editorial_cream_now():
    """ADR-073 superseded ADR-071's one exception here: academic/
    lecture document types used to get blue_academic specifically, on
    the reasoning that editorial_cream wasn't yet established as THE
    theme. Now that "editorial cream only" is an explicit, direct
    instruction, that exception is gone — document_type no longer
    changes which theme a document upload gets. Nothing is actually
    lost for academic content: editorial_cream's own font_set_id is
    already "serif", the property the old exception existed to
    guarantee."""
    for doc_type in ("academic", "lecture", "general"):
        outline = make_outline(document_type=doc_type)
        recipe = RuleBasedDesignAdapter().apply_theme(
            project_id="p1", source_text="doc text", outline=outline,
            theme=Theme(), audience_type="general", language="en",
        )
        assert recipe.theme.color_set_id == "editorial_cream", f"failed for document_type={doc_type!r}"


def test_explicitly_requested_theme_is_still_respected():
    """Neither ADR-071 nor ADR-073 touch what happens when a caller
    explicitly names a theme — only what "no theme requested" resolves
    to. Nothing currently in the product does this anymore (variety.
    pick_theme_variant only ever returns "editorial_cream" now, ADR-073),
    but the resolution logic itself still honors an explicit request if
    one is ever made — e.g. directly through this port, or by future
    code — rather than silently overriding it."""
    outline = make_outline()
    requested = _KNOWN_THEMES["gradient_violet"]
    recipe = RuleBasedDesignAdapter().apply_theme(
        project_id="p1", source_text="doc text", outline=outline,
        theme=requested, audience_type="general", language="en",
    )
    assert recipe.theme.color_set_id == "gradient_violet"
