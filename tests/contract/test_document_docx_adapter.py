"""Contract tests for DocumentDocxExportAdapter (ADR-041, v3 Phase 3)."""

import io
from docx import Document
from backend.models.recipe import Recipe, Outline, Slide, ContentBlock, BlockType, StructureSource, Theme
from backend.adapters.export.document_docx_adapter import DocumentDocxExportAdapter


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


def test_format_id():
    assert DocumentDocxExportAdapter().format_id() == "document_docx"


def test_produces_a_valid_docx():
    output = DocumentDocxExportAdapter().export(make_recipe())
    doc = Document(io.BytesIO(output))  # raises if not a real docx
    assert len(doc.paragraphs) > 0


def test_first_slide_becomes_the_title_not_a_numbered_slide_heading():
    output = DocumentDocxExportAdapter().export(make_recipe())
    doc = Document(io.BytesIO(output))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "AI-First Market Report" in full_text
    assert "Slide 1" not in full_text  # this is a document, not slide-notes framing


def test_section_headings_present_for_every_non_title_slide():
    output = DocumentDocxExportAdapter().export(make_recipe())
    doc = Document(io.BytesIO(output))
    heading_texts = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
    assert "Executive Summary" in heading_texts
    assert "Key Findings" in heading_texts


def test_single_sentence_bullet_runs_as_a_paragraph_not_a_list_item():
    output = DocumentDocxExportAdapter().export(make_recipe())
    doc = Document(io.BytesIO(output))
    # The Executive Summary slide has exactly one bullet that reads as a
    # full sentence -> should be a plain paragraph, not "List Bullet" style.
    matching = [p for p in doc.paragraphs if "grew significantly" in p.text]
    assert len(matching) == 1
    assert matching[0].style.name != "List Bullet"


def test_multiple_bullets_stay_a_real_bullet_list():
    output = DocumentDocxExportAdapter().export(make_recipe())
    doc = Document(io.BytesIO(output))
    bullet_paragraphs = [p for p in doc.paragraphs if p.style.name == "List Bullet"]
    bullet_texts = [p.text for p in bullet_paragraphs]
    assert "Adoption is accelerating" in bullet_texts
    assert "Pricing pressure is increasing" in bullet_texts


def test_speaker_notes_are_not_rendered_in_the_document():
    """Notes exist for a presenter reading a deck aloud — irrelevant
    once the deliverable IS the document, unlike the notes_docx
    adapter where they're the entire point."""
    output = DocumentDocxExportAdapter().export(make_recipe())
    doc = Document(io.BytesIO(output))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Mention this only if asked." not in full_text


def test_empty_outline_still_produces_a_valid_docx():
    empty_outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[])
    empty_recipe = Recipe.new(project_id="p1", source_text="Topic: test", outline=empty_outline,
                               theme=Theme(), audience_type="general", language="en")
    output = DocumentDocxExportAdapter().export(empty_recipe)
    doc = Document(io.BytesIO(output))  # must not raise
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Untitled Document" in full_text
