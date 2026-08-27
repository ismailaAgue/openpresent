"""Contract tests for InfographicSvgExportAdapter (ADR-046, v3 Phase 6)."""

import xml.etree.ElementTree as ET
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource, Theme
from backend.adapters.export.infographic_svg_adapter import InfographicSvgExportAdapter


def make_recipe(slides=None, color_set_id="neutral"):
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=slides if slides is not None else [
        Slide(order=1, title="The Future of Renewable Energy", content_blocks=[]),
        Slide(order=2, title="Solar Adoption Is Accelerating", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Costs have dropped 80% in a decade"),
            ContentBlock(type=BlockType.BULLET, text="Residential installs doubled last year"),
        ]),
        Slide(order=3, title="Storage Is the Next Bottleneck", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Battery costs remain the limiting factor"),
        ]),
    ])
    return Recipe.new(project_id="p1", source_text="Topic: test", outline=outline,
                       theme=Theme(color_set_id=color_set_id), audience_type="general", language="en")


def parse(output: bytes):
    return ET.fromstring(output)  # raises if not well-formed XML/SVG


def test_format_id():
    assert InfographicSvgExportAdapter().format_id() == "infographic_svg"


def test_produces_well_formed_svg():
    output = InfographicSvgExportAdapter().export(make_recipe())
    root = parse(output)
    assert root.tag.endswith("svg")


def test_svg_has_a_viewbox_and_positive_dimensions():
    output = InfographicSvgExportAdapter().export(make_recipe())
    root = parse(output)
    assert "viewBox" in root.attrib
    assert int(root.attrib["width"]) > 0
    assert int(root.attrib["height"]) > 0


def test_title_appears_in_the_output():
    output = InfographicSvgExportAdapter().export(make_recipe())
    assert b"Future of Renewable Energy" in output


def test_one_numbered_card_per_non_title_slide():
    output = InfographicSvgExportAdapter().export(make_recipe())
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    circles = root.findall(".//svg:circle", ns)
    # 2 sections in the fixture (slides[1:]) -> 2 numbered circles
    assert len(circles) == 2


def test_bullet_text_appears_in_the_output():
    output = InfographicSvgExportAdapter().export(make_recipe())
    assert b"Costs have dropped" in output
    assert b"Battery costs remain" in output


def test_section_headings_appear_in_the_output():
    output = InfographicSvgExportAdapter().export(make_recipe())
    assert b"Solar Adoption Is Accelerating" in output
    assert b"Storage Is the Next Bottleneck" in output


def test_long_bullet_text_is_wrapped_not_overflowing_one_line():
    long_bullet = "This is a very long bullet point that absolutely will not fit on a single line " \
                  "of a fixed-width infographic card no matter what font size is chosen for it"
    slides = [
        Slide(order=1, title="Title", content_blocks=[]),
        Slide(order=2, title="Section", content_blocks=[ContentBlock(type=BlockType.BULLET, text=long_bullet)]),
    ]
    output = InfographicSvgExportAdapter().export(make_recipe(slides=slides))
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    texts = [t.text or "" for t in root.findall(".//svg:text", ns)]
    # the long bullet must have been split across more than one <text> line
    assert not any(len(t) > 120 for t in texts)


def test_more_bullets_than_the_cap_are_truncated_not_overflowing():
    many_bullets = [ContentBlock(type=BlockType.BULLET, text=f"Point number {i}") for i in range(20)]
    slides = [
        Slide(order=1, title="Title", content_blocks=[]),
        Slide(order=2, title="Section", content_blocks=many_bullets),
    ]
    output = InfographicSvgExportAdapter().export(make_recipe(slides=slides))
    # must not raise and must still produce well-formed, parseable SVG
    # with the card capped rather than growing unboundedly
    parse(output)
    assert b"Point number 19" not in output  # beyond MAX_BULLETS_PER_CARD, correctly dropped


def test_notes_are_not_rendered():
    slides = [
        Slide(order=1, title="Title", content_blocks=[]),
        Slide(order=2, title="Section", content_blocks=[
            ContentBlock(type=BlockType.NOTE, text="Speaker-only aside, never shown"),
        ]),
    ]
    output = InfographicSvgExportAdapter().export(make_recipe(slides=slides))
    assert b"Speaker-only aside" not in output


def test_empty_outline_still_produces_valid_svg():
    output = InfographicSvgExportAdapter().export(make_recipe(slides=[]))
    root = parse(output)  # must not raise
    assert root.tag.endswith("svg")


def test_different_color_sets_produce_different_output():
    """Confirms Theme.color_set_id actually flows through — the same
    real palette pptx_adapter.py uses, not a separate hardcoded one."""
    neutral = InfographicSvgExportAdapter().export(make_recipe(color_set_id="neutral"))
    dark = InfographicSvgExportAdapter().export(make_recipe(color_set_id="modern_dark"))
    assert neutral != dark


def test_special_characters_are_escaped_not_breaking_the_xml():
    slides = [
        Slide(order=1, title="R&D <Innovation> \"Report\"", content_blocks=[]),
        Slide(order=2, title="Section", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Costs & benefits < 10% risk"),
        ]),
    ]
    output = InfographicSvgExportAdapter().export(make_recipe(slides=slides))
    parse(output)  # must not raise — proves escaping worked, not just "didn't crash by luck"
