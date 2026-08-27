"""
DocumentDocxExportAdapter — ADR-041 (v3 Phase 3, "Documents" output type).

Renders the exact same Recipe/Outline the slide pipeline produces, but
as a flowing Word document instead of a deck: each Slide becomes a
document section (its title -> a heading, its bullets -> either a real
bullet list or, when the section reads more like prose, run together
into paragraphs), rather than being laid out for on-screen display.

This is deliberately NOT the same thing as SpeakerNotesDocxExportAdapter
(docx_notes_adapter.py) — that one is a presenter's companion aid
("Slide 3: Market Opportunity" headers, "On-slide content:" labels).
This adapter is meant to BE the deliverable itself: a real report,
proposal, or exec summary a reader opens and reads top to bottom, with
no reference to slides anywhere in it. Per the v3 roadmap's Phase 3:
reuse Strategy/Outline/Content generation as-is (same Outline model,
same generate_presentation_from_topic()) and only Layout/Export differ
— this file is that "Export differs" half. There is no separate
document-generation pipeline; export_format="document_docx" is a
normal ExportPort choice on the same engine call as every other format.

Deliberately conservative about turning bullets into prose: forcing
every bullet list into paragraph text is a common way AI-authored
documents end up reading worse than well-formatted decks, not better,
so the default is to keep bullets as a real Word bullet list per
section and only merge them into a paragraph when a slide is a single,
sentence-length block (see _should_run_as_paragraph) — i.e. content
that was written to read as a sentence, not force everything into one
shape regardless of how it was actually written.
"""

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from backend.ports.export import ExportPort
from backend.models.recipe import Recipe, BlockType


class DocumentDocxExportAdapter(ExportPort):
    def format_id(self) -> str:
        return "document_docx"

    def export(self, recipe: Recipe) -> bytes:
        import io

        slides = sorted(recipe.outline.slides, key=lambda s: s.order)
        doc = Document()

        self._add_title_page(doc, slides[0].title if slides else "Untitled Document")

        # slides[0] became the title page above; everything else is a
        # real section. A deck's closing slide (e.g. "Questions?",
        # "Contact Information") reads fine as a document's final
        # section too — no special-casing needed there.
        for slide in slides[1:]:
            doc.add_heading(slide.title, level=1)

            bullets = [b.text for b in slide.content_blocks if b.type == BlockType.BULLET and b.text]
            if self._should_run_as_paragraph(bullets):
                doc.add_paragraph(" ".join(bullets))
            else:
                for bullet in bullets:
                    doc.add_paragraph(bullet, style="List Bullet")

            # Notes exist in the model to support a *presenter* reading
            # a deck aloud — irrelevant once the deliverable is the
            # document itself, so intentionally not rendered here
            # (unlike SpeakerNotesDocxExportAdapter, where they're the
            # entire point).

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    @staticmethod
    def _should_run_as_paragraph(bullets: list[str]) -> bool:
        """A single bullet that already reads as a full sentence (ends
        in terminal punctuation) was authored as prose, not a list —
        keep it that way. Multiple bullets, or a lone short fragment,
        stay a real bullet list."""
        return len(bullets) == 1 and bullets[0].rstrip().endswith((".", "!", "?"))

    @staticmethod
    def _add_title_page(doc: Document, title: str) -> None:
        heading = doc.add_heading(title, level=0)
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_page_break()
