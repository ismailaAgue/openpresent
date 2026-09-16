"""
RuleBasedDesignAdapter's default-theme resolution — ADR-071.

No prior test file covered apply_theme()'s own theme_key resolution
directly (test_ai_generate_engine.py covers the topic-first pipeline's
separate variety.pick_theme_variant() path, a different mechanism).
This covers the specific change: a document upload (or any caller)
with no theme explicitly requested used to land on "default" (plain
neutral) unconditionally unless the document type called for serif —
meaning 7 of the 9 themes added since ADR-030/059/062 were never
reachable from this path at all. editorial_cream is now that default.
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


def test_serif_leaning_document_types_still_get_academic_not_editorial():
    """A stated, deliberate exception, unchanged by ADR-071: academic/
    lecture documents get the blue_academic serif theme specifically,
    not editorial_cream — this distinction predates ADR-071 and isn't
    what it was about."""
    for doc_type in ("academic", "lecture"):
        outline = make_outline(document_type=doc_type)
        recipe = RuleBasedDesignAdapter().apply_theme(
            project_id="p1", source_text="doc text", outline=outline,
            theme=Theme(), audience_type="general", language="en",
        )
        assert recipe.theme.color_set_id == "blue_academic", f"failed for document_type={doc_type!r}"


def test_explicitly_requested_theme_is_still_respected():
    """ADR-071 only changes what happens with NO explicit theme — a
    caller that names one (topic-first generation always does, via
    variety.pick_theme_variant) must still get exactly that theme."""
    outline = make_outline()
    requested = _KNOWN_THEMES["gradient_violet"]
    recipe = RuleBasedDesignAdapter().apply_theme(
        project_id="p1", source_text="doc text", outline=outline,
        theme=requested, audience_type="general", language="en",
    )
    assert recipe.theme.color_set_id == "gradient_violet"
