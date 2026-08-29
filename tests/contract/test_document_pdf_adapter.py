"""Contract tests for DocumentPdfExportAdapter (ADR-055).

Mirrors test_document_docx_adapter.py's cases wherever the same
behavior applies (same content model, same _all_read_as_prose rule) —
this adapter is meant to be the PDF sibling of that one, not a
different design. Uses pypdf (already a project dependency, for PDF
ingestion) to extract text back out and assert on it, since reportlab
has no equivalent of python-docx's read-back API.
"""

import io
from pypdf import PdfReader
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource, Theme
from backend.adapters.export.document_pdf_adapter import DocumentPdfExportAdapter


def make_recipe(slides=None):
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=slides or [
        Slide(order=1, title="AI-First Market Report", content_blocks=[]),
        Slide(order=2, title="Executive Summary", content_blocks=[
            ContentBlock(
                type=BlockType.BULLET,
                text="The market for AI-first tools grew significantly this year.",
            ),
        ]),
        Slide(order=3, title="Key Findings", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Adoption is accelerating"),
            ContentBlock(type=BlockType.BULLET, text="Pricing pressure is increasing"),
            ContentBlock(type=BlockType.NOTE, text="Mention this only if asked."),
        ]),
    ])
    return Recipe.new(project_id="p1", source_text="Topic: test", outline=outline,
                       theme=Theme(), audience_type="general", language="en")


def extract_text(output: bytes) -> str:
    reader = PdfReader(io.BytesIO(output))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_format_id():
    assert DocumentPdfExportAdapter().format_id() == "document_pdf"


def test_produces_a_valid_pdf():
    output = DocumentPdfExportAdapter().export(make_recipe())
    assert output.startswith(b"%PDF")
    reader = PdfReader(io.BytesIO(output))  # raises if not a real PDF
    assert len(reader.pages) >= 2  # title page + at least one section


def test_first_slide_becomes_the_title_not_a_numbered_slide_heading():
    full_text = extract_text(DocumentPdfExportAdapter().export(make_recipe()))
    assert "AI-First Market Report" in full_text
    assert "Slide 1" not in full_text  # this is a document, not slide-notes framing


def test_section_headings_present_for_every_non_title_slide():
    full_text = extract_text(DocumentPdfExportAdapter().export(make_recipe()))
    assert "Executive Summary" in full_text
    assert "Key Findings" in full_text


def test_multiple_bullets_render():
    full_text = extract_text(DocumentPdfExportAdapter().export(make_recipe()))
    assert "Adoption is accelerating" in full_text
    assert "Pricing pressure is increasing" in full_text


def test_speaker_notes_are_not_rendered_in_the_document():
    full_text = extract_text(DocumentPdfExportAdapter().export(make_recipe()))
    assert "Mention this only if asked." not in full_text


def test_empty_outline_still_produces_a_valid_pdf():
    empty_outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[])
    empty_recipe = Recipe.new(project_id="p1", source_text="Topic: test", outline=empty_outline,
                               theme=Theme(), audience_type="general", language="en")
    output = DocumentPdfExportAdapter().export(empty_recipe)
    full_text = extract_text(output)  # must not raise
    assert "Untitled Document" in full_text


def test_multiple_paragraph_length_bullets_become_multiple_real_paragraphs():
    """Same ADR-054 content-shaping rule document_docx relies on:
    each sentence-ending bullet is real prose, not a bulleted list."""
    slides = [
        Slide(order=1, title="Report", content_blocks=[]),
        Slide(order=2, title="Market Overview", content_blocks=[
            ContentBlock(type=BlockType.BULLET,
                         text="The market grew substantially this year, driven by strong demand."),
            ContentBlock(type=BlockType.BULLET,
                         text="Competition also intensified, with several new entrants."),
        ]),
    ]
    full_text = extract_text(DocumentPdfExportAdapter().export(make_recipe(slides=slides)))
    assert "grew substantially" in full_text
    assert "intensified" in full_text


def test_different_themes_produce_different_output_bytes():
    """Theme color is embedded directly in the PDF content stream —
    a different accent/title color must produce different bytes, the
    PDF-adapter equivalent of document_docx's heading-color-per-theme
    test (reportlab has no read-back API for a run's exact RGB the way
    python-docx does, so this checks the render actually changed
    rather than decoding the content stream by hand)."""
    recipe_a = make_recipe()
    recipe_a.theme.color_set_id = "neutral"
    recipe_b = make_recipe()
    recipe_b.theme.color_set_id = "modern_dark"

    output_a = DocumentPdfExportAdapter().export(recipe_a)
    output_b = DocumentPdfExportAdapter().export(recipe_b)
    assert output_a != output_b


def test_special_characters_do_not_break_rendering():
    """reportlab's Paragraph parses its input as markup, not plain
    text — raw '&'/'<'/'>' in generated content must not raise or
    corrupt the page (see _escape's docstring)."""
    slides = [
        Slide(order=1, title="R&D <Update>", content_blocks=[]),
        Slide(order=2, title="Findings", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Revenue grew 5% > forecast, per R&D estimates."),
        ]),
    ]
    output = DocumentPdfExportAdapter().export(make_recipe(slides=slides))  # must not raise
    full_text = extract_text(output)
    assert "R&D" in full_text
