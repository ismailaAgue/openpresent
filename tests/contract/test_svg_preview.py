"""Tests for SvgPreviewAdapter — ADR-061.

See backend/adapters/preview/svg_preview.py's module docstring for
why this exists: a themed visual preview without needing LibreOffice
in production. Verified by actually rendering real samples to PNG and
comparing against the real pptx export (see ADR-061's Verification
section) — these tests cover structural correctness (valid SVG,
correct slide count, theme-appropriate shapes present/absent) rather
than re-deriving what a rendered image should look like pixel by pixel.
"""

import xml.dom.minidom as minidom
from backend.adapters.preview.svg_preview import SvgPreviewAdapter
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource, Theme


def make_recipe(theme_id="neutral", slides=None) -> Recipe:
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=slides or [
        Slide(order=1, title="Cover Slide", content_blocks=[]),
        Slide(order=2, title="Details", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="First point"),
            ContentBlock(type=BlockType.BULLET, text="Second point"),
        ]),
    ])
    return Recipe.new(project_id="p1", source_text="Topic: test", outline=outline,
                       theme=Theme(color_set_id=theme_id), audience_type="general", language="en")


def test_returns_one_entry_per_slide_in_order():
    result = SvgPreviewAdapter().render(make_recipe())
    assert [s["order"] for s in result] == [1, 2]


def test_every_svg_is_well_formed_xml():
    result = SvgPreviewAdapter().render(make_recipe())
    for s in result:
        minidom.parseString(s["svg"])  # raises if not well-formed


def test_special_characters_do_not_break_the_svg():
    """SVG text content needs XML escaping — raw '&'/'<'/'>' from
    generated content would otherwise produce invalid XML, the SVG
    equivalent of the pdf/docx adapters' own _escape() bug class."""
    slides = [
        Slide(order=1, title="R&D <Update> for Q3", content_blocks=[]),
        Slide(order=2, title="Growth & Revenue", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Revenue grew 5% > forecast, per R&D estimates"),
        ]),
    ]
    result = SvgPreviewAdapter().render(make_recipe(slides=slides))
    for s in result:
        minidom.parseString(s["svg"])  # must not raise
    assert "R&amp;D" in result[0]["svg"]


def test_empty_outline_does_not_raise():
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[])
    recipe = Recipe.new(project_id="p1", source_text="Topic: test", outline=outline,
                         theme=Theme(), audience_type="general", language="en")
    result = SvgPreviewAdapter().render(recipe)
    assert result == []


def test_first_slide_always_renders_as_a_title_slide():
    """Matches PptxExportAdapter's own convention: slides[0] is always
    the title slide regardless of its layout_type."""
    slides = [
        Slide(order=1, title="Cover", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="should not appear as bullets"),
        ], layout_type="statistics"),
    ]
    result = SvgPreviewAdapter().render(make_recipe(slides=slides))
    assert "should not appear as bullets" not in result[0]["svg"]


def test_gradient_violet_theme_includes_a_gradient_definition():
    result = SvgPreviewAdapter().render(make_recipe("gradient_violet"))
    assert "linearGradient" in result[0]["svg"]  # title slide's large blob


def test_minimal_mono_theme_has_no_corner_decoration_shapes():
    result = SvgPreviewAdapter().render(make_recipe("minimal_mono"))
    for s in result:
        assert "<circle" not in s["svg"]


def test_statistics_slide_with_chip_theme_renders_tinted_cards():
    slides = [
        Slide(order=1, title="Cover", content_blocks=[]),
        Slide(order=2, title="Key Metrics", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="$320,820M raised across 2018-2020"),
            ContentBlock(type=BlockType.BULLET, text="90% client satisfaction rate"),
            ContentBlock(type=BlockType.BULLET, text="415K happy customers served"),
        ], layout_type="statistics"),
    ]
    result = SvgPreviewAdapter().render(make_recipe("gradient_violet", slides=slides))
    stats_svg = result[1]["svg"]
    assert stats_svg.count('rx="14"') == 3  # one rounded card per stat
    assert "$320,820M" in stats_svg
    assert "90%" in stats_svg
    assert "415K" in stats_svg


def test_statistics_slide_without_chip_theme_renders_plain_text():
    slides = [
        Slide(order=1, title="Cover", content_blocks=[]),
        Slide(order=2, title="Key Metrics", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="90% satisfaction"),
        ], layout_type="statistics"),
    ]
    result = SvgPreviewAdapter().render(make_recipe("minimal_mono", slides=slides))  # stat_chip=False
    assert 'rx="14"' not in result[1]["svg"]


def test_statistics_slide_without_chip_theme_renders_a_bar_chart_when_chartable():
    """ADR-064 — the preview must match the real export: 2+ same-unit
    stats on a stat_chip=False theme now render as an actual bar chart
    (rects scaled to value, original display text per bar) instead of
    plain centered text, mirroring PptxExportAdapter's own native
    chart for the identical case."""
    slides = [
        Slide(order=1, title="Cover", content_blocks=[]),
        Slide(order=2, title="Key Metrics", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="42% renewable adoption"),
            ContentBlock(type=BlockType.BULLET, text="31% wind share"),
            ContentBlock(type=BlockType.BULLET, text="18% hydro share"),
        ], layout_type="statistics"),
    ]
    result = SvgPreviewAdapter().render(make_recipe("minimal_mono", slides=slides))  # stat_chip=False
    stats_svg = result[1]["svg"]
    # 2 baseline rects (background + title accent bar) + 1 bar per stat
    assert stats_svg.count("<rect") == 5
    assert "42%" in stats_svg
    assert "31%" in stats_svg
    assert "18%" in stats_svg
    assert "renewable" in stats_svg
    # the tallest bar (42%, the largest value) must actually be taller
    # than the shortest (18%) — a chart that doesn't scale by value
    # isn't a chart, it's three identical rectangles with numbers on them.
    import re
    heights = [int(h) for h in re.findall(r'<rect[^>]*height="(\d+)"', stats_svg)]
    assert max(heights) > min(heights)


def test_statistics_slide_without_chip_theme_falls_back_for_mixed_units():
    """Same non-chartability rule as the real export (imported from
    pptx_adapter, not reimplemented) — a dollar figure next to a
    percentage stays plain text, doesn't become a misleading chart."""
    slides = [
        Slide(order=1, title="Cover", content_blocks=[]),
        Slide(order=2, title="Key Metrics", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="$50B market size"),
            ContentBlock(type=BlockType.BULLET, text="97% satisfaction"),
        ], layout_type="statistics"),
    ]
    result = SvgPreviewAdapter().render(make_recipe("minimal_mono", slides=slides))
    stats_svg = result[1]["svg"]
    # 2 baseline rects (background + title accent bar), no bars added
    assert stats_svg.count("<rect") == 2
    assert "$50B market size" in stats_svg
    assert "97% satisfaction" in stats_svg


def test_bullet_slide_has_one_colored_marker_per_bullet():
    result = SvgPreviewAdapter().render(make_recipe())
    bullet_svg = result[1]["svg"]
    # each bullet gets a small accent-colored square marker (10x10)
    assert bullet_svg.count('width="10" height="10"') == 2


def test_comparison_and_process_layouts_fall_back_to_themed_bullets():
    """Stated scope limit (module docstring) — not a silent gap: both
    still render, just without their pptx-specific card/badge
    treatment, using the same themed bullet rendering every other
    non-title, non-statistics slide gets."""
    slides = [
        Slide(order=1, title="Cover", content_blocks=[]),
        Slide(order=2, title="Us vs Them", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Faster"),
            ContentBlock(type=BlockType.BULLET, text="Slower"),
        ], layout_type="comparison"),
        Slide(order=3, title="Steps", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="First, sign up"),
        ], layout_type="process"),
    ]
    result = SvgPreviewAdapter().render(make_recipe(slides=slides))
    assert len(result) == 3
    for s in result[1:]:
        minidom.parseString(s["svg"])  # renders without raising either way
