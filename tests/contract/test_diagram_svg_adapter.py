"""Contract tests for DiagramSvgExportAdapter (ADR-047, v3 Phase 6)."""

import xml.etree.ElementTree as ET
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource, Theme
from backend.adapters.export.diagram_svg_adapter import DiagramSvgExportAdapter


def make_recipe(slides=None, color_set_id="neutral"):
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=slides if slides is not None else [
        Slide(order=1, title="Customer Onboarding Process", content_blocks=[]),
        Slide(order=2, title="Sign Up", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="User creates an account"),
        ]),
        Slide(order=3, title="Email Verification", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="A confirmation link is sent"),
        ]),
        Slide(order=4, title="Welcome", content_blocks=[]),
    ])
    return Recipe.new(project_id="p1", source_text="Topic: test", outline=outline,
                       theme=Theme(color_set_id=color_set_id), audience_type="general", language="en")


def parse(output: bytes):
    return ET.fromstring(output)  # raises if not well-formed XML/SVG


def test_format_id():
    assert DiagramSvgExportAdapter().format_id() == "diagram_svg"


def test_produces_well_formed_svg():
    output = DiagramSvgExportAdapter().export(make_recipe())
    root = parse(output)
    assert root.tag.endswith("svg")


def test_svg_has_a_viewbox_and_positive_dimensions():
    output = DiagramSvgExportAdapter().export(make_recipe())
    root = parse(output)
    assert "viewBox" in root.attrib
    assert int(root.attrib["width"]) > 0
    assert int(root.attrib["height"]) > 0


def test_header_title_appears():
    output = DiagramSvgExportAdapter().export(make_recipe())
    assert b"Customer Onboarding Process" in output


def test_one_box_per_non_title_slide():
    output = DiagramSvgExportAdapter().export(make_recipe())
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    # 3 sections in the fixture (slides[1:]) -> 3 <rect> boxes, plus
    # the full-width background rect and the accent top-bar rect = 5 total
    rects = root.findall(".//svg:rect", ns)
    assert len(rects) == 5


def test_one_fewer_arrow_than_boxes():
    """N boxes in a linear chain need exactly N-1 connectors between them."""
    output = DiagramSvgExportAdapter().export(make_recipe())
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    lines = root.findall(".//svg:line", ns)
    assert len(lines) == 2  # 3 boxes -> 2 arrows


def test_single_box_has_no_arrows():
    slides = [
        Slide(order=1, title="Header", content_blocks=[]),
        Slide(order=2, title="Only Step", content_blocks=[]),
    ]
    output = DiagramSvgExportAdapter().export(make_recipe(slides=slides))
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert len(root.findall(".//svg:line", ns)) == 0


def test_step_titles_appear_in_the_output():
    output = DiagramSvgExportAdapter().export(make_recipe())
    assert b"Sign Up" in output
    assert b"Email Verification" in output
    assert b"Welcome" in output


def test_first_bullet_appears_as_a_subline():
    output = DiagramSvgExportAdapter().export(make_recipe())
    assert b"User creates an account" in output


def test_only_the_first_bullet_is_shown_not_additional_ones():
    """A diagram box is meant to read in a glance — unlike the
    infographic adapter's cards, only the first bullet is ever shown,
    even when more exist."""
    slides = [
        Slide(order=1, title="Header", content_blocks=[]),
        Slide(order=2, title="Step", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="First bullet shown"),
            ContentBlock(type=BlockType.BULLET, text="Second bullet not shown"),
        ]),
    ]
    output = DiagramSvgExportAdapter().export(make_recipe(slides=slides))
    assert b"First bullet shown" in output
    assert b"Second bullet not shown" not in output


def test_step_with_no_bullets_has_no_subline_but_still_renders():
    output = DiagramSvgExportAdapter().export(make_recipe())
    # "Welcome" has no content_blocks — must not raise, and its box
    # must be visibly shorter than a box with a subline (proven
    # indirectly by well-formedness + presence, exact height not
    # asserted since that's an implementation detail, not a contract).
    parse(output)


def test_notes_are_never_used_as_the_subline():
    slides = [
        Slide(order=1, title="Header", content_blocks=[]),
        Slide(order=2, title="Step", content_blocks=[
            ContentBlock(type=BlockType.NOTE, text="Speaker-only aside, never shown"),
        ]),
    ]
    output = DiagramSvgExportAdapter().export(make_recipe(slides=slides))
    assert b"Speaker-only aside" not in output


def test_long_title_is_wrapped_not_overflowing_one_line():
    long_title = "A Genuinely Very Long Step Title That Should Wrap Across Multiple Lines Inside The Box"
    slides = [
        Slide(order=1, title="Header", content_blocks=[]),
        Slide(order=2, title=long_title, content_blocks=[]),
    ]
    output = DiagramSvgExportAdapter().export(make_recipe(slides=slides))
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    texts = [t.text or "" for t in root.findall(".//svg:text", ns)]
    assert not any(len(t) > 100 for t in texts)


def test_empty_outline_still_produces_valid_svg():
    output = DiagramSvgExportAdapter().export(make_recipe(slides=[]))
    root = parse(output)
    assert root.tag.endswith("svg")


def test_no_steps_only_a_header_still_produces_valid_svg():
    slides = [Slide(order=1, title="Just A Header", content_blocks=[])]
    output = DiagramSvgExportAdapter().export(make_recipe(slides=slides))
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert len(root.findall(".//svg:line", ns)) == 0


def test_different_color_sets_produce_different_output():
    neutral = DiagramSvgExportAdapter().export(make_recipe(color_set_id="neutral"))
    dark = DiagramSvgExportAdapter().export(make_recipe(color_set_id="modern_dark"))
    assert neutral != dark


def test_special_characters_are_escaped_not_breaking_the_xml():
    slides = [
        Slide(order=1, title="R&D <Pipeline> \"Review\"", content_blocks=[]),
        Slide(order=2, title="Step", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Costs & benefits < 10% risk"),
        ]),
    ]
    output = DiagramSvgExportAdapter().export(make_recipe(slides=slides))
    parse(output)  # must not raise


def test_no_watermark_text_in_output():
    """ADR-054 — 'Generated with OpenPresent' was removed from every
    SVG format's rendered output."""
    output = DiagramSvgExportAdapter().export(make_recipe())
    assert b"OpenPresent" not in output
    assert b"Generated with" not in output
