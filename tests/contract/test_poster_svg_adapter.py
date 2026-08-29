"""Contract tests for PosterSvgExportAdapter (ADR-048, v3 Phase 6)."""

import xml.etree.ElementTree as ET
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource, Theme
from backend.adapters.export.poster_svg_adapter import PosterSvgExportAdapter, MAX_HIGHLIGHTS


def make_recipe(slides=None, color_set_id="neutral"):
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=slides if slides is not None else [
        Slide(order=1, title="The Future of Renewable Energy", content_blocks=[]),
        Slide(order=2, title="Solar Adoption Is Accelerating", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Costs dropped 80% in a decade"),
        ]),
        Slide(order=3, title="Storage Is the Next Bottleneck", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Battery costs remain the limiting factor"),
        ]),
    ])
    return Recipe.new(project_id="p1", source_text="Topic: test", outline=outline,
                       theme=Theme(color_set_id=color_set_id), audience_type="general", language="en")


def parse(output: bytes):
    return ET.fromstring(output)  # raises if not well-formed XML/SVG


def get_texts(output: bytes) -> list[str]:
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    return [t.text or "" for t in root.findall(".//svg:text", ns)]


def test_format_id():
    assert PosterSvgExportAdapter().format_id() == "poster_svg"


def test_produces_well_formed_svg():
    output = PosterSvgExportAdapter().export(make_recipe())
    root = parse(output)
    assert root.tag.endswith("svg")


def test_canvas_is_a_fixed_portrait_size_not_variable():
    """Unlike the infographic/diagram adapters (which grow with
    content), a poster is meant to be one fixed shareable-image size —
    confirmed unchanged regardless of how much or little content."""
    small = PosterSvgExportAdapter().export(make_recipe(slides=[
        Slide(order=1, title="Just a title", content_blocks=[]),
    ]))
    large = PosterSvgExportAdapter().export(make_recipe())
    root_small, root_large = parse(small), parse(large)
    assert root_small.attrib["width"] == root_large.attrib["width"]
    assert root_small.attrib["height"] == root_large.attrib["height"]


def test_headline_appears():
    output = PosterSvgExportAdapter().export(make_recipe())
    assert "Future of Renewable Energy" in " ".join(get_texts(output))


def test_no_numbered_markers_present():
    """The one deliberate structural difference from the infographic/
    diagram adapters, stated in the module docstring: poster highlights
    aren't a sequence, so no numbers should appear anywhere in the text
    layer (a bare "1", "2", "3" as their own text node, the way the
    other two adapters render step/section numbers)."""
    output = PosterSvgExportAdapter().export(make_recipe())
    texts = get_texts(output)
    assert "1" not in texts
    assert "2" not in texts
    assert "3" not in texts


def test_highlights_capped_at_max_highlights():
    slides = [Slide(order=1, title="Header", content_blocks=[])] + [
        Slide(order=i + 2, title=f"Section {i}", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text=f"Highlight number {i}")
        ]) for i in range(10)
    ]
    output = PosterSvgExportAdapter().export(make_recipe(slides=slides))
    full_text = " ".join(get_texts(output))
    shown = sum(1 for i in range(10) if f"Highlight number {i}" in full_text)
    assert shown == MAX_HIGHLIGHTS


def test_section_with_no_bullets_falls_back_to_its_own_title_as_the_highlight():
    """A poster can't afford an empty highlight line just because a
    section happened to have no bullets — the section title itself is
    still a true claim about the topic."""
    slides = [
        Slide(order=1, title="Header", content_blocks=[]),
        Slide(order=2, title="A Section With No Bullets At All", content_blocks=[]),
    ]
    output = PosterSvgExportAdapter().export(make_recipe(slides=slides))
    assert "A Section With No Bullets At All" in " ".join(get_texts(output))


def test_notes_are_never_used_as_a_highlight():
    slides = [
        Slide(order=1, title="Header", content_blocks=[]),
        Slide(order=2, title="Section", content_blocks=[
            ContentBlock(type=BlockType.NOTE, text="Speaker-only aside, never shown"),
        ]),
    ]
    output = PosterSvgExportAdapter().export(make_recipe(slides=slides))
    assert "Speaker-only aside" not in " ".join(get_texts(output))
    # falls back to the section's own title instead, per the rule above
    assert "Section" in " ".join(get_texts(output))


def test_divider_absent_when_there_are_zero_highlights():
    """A divider introducing zero supporting content would be
    unjustified decoration — the module was fixed during development
    (via visual inspection, not a test catching it first) to only
    render the divider when there's actually something below it."""
    slides = [Slide(order=1, title="Just A Header", content_blocks=[])]
    output = PosterSvgExportAdapter().export(make_recipe(slides=slides))
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert len(root.findall(".//svg:line", ns)) == 0


def test_divider_present_when_there_is_at_least_one_highlight():
    output = PosterSvgExportAdapter().export(make_recipe())
    root = parse(output)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert len(root.findall(".//svg:line", ns)) == 1


def test_long_headline_is_wrapped_not_a_single_overflowing_line():
    long_title = "A Genuinely Long Headline About The Future Of Renewable Energy Systems Worldwide"
    slides = [Slide(order=1, title=long_title, content_blocks=[])]
    output = PosterSvgExportAdapter().export(make_recipe(slides=slides))
    texts = get_texts(output)
    assert not any(len(t) > 60 for t in texts)


def test_empty_outline_still_produces_valid_svg():
    output = PosterSvgExportAdapter().export(make_recipe(slides=[]))
    root = parse(output)
    assert root.tag.endswith("svg")


def test_different_color_sets_produce_different_output():
    neutral = PosterSvgExportAdapter().export(make_recipe(color_set_id="neutral"))
    dark = PosterSvgExportAdapter().export(make_recipe(color_set_id="modern_dark"))
    assert neutral != dark


def test_special_characters_are_escaped_not_breaking_the_xml():
    slides = [
        Slide(order=1, title="R&D <Launch> \"Event\"", content_blocks=[]),
        Slide(order=2, title="Section", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Costs & benefits < 10% risk"),
        ]),
    ]
    output = PosterSvgExportAdapter().export(make_recipe(slides=slides))
    parse(output)  # must not raise


def test_no_watermark_text_in_output():
    """ADR-054 — 'Generated with OpenPresent' was removed from every
    SVG format's rendered output."""
    output = PosterSvgExportAdapter().export(make_recipe())
    assert b"OpenPresent" not in output
    assert b"Generated with" not in output
