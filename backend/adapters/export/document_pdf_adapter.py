"""
DocumentPdfExportAdapter — ADR-055 (v3 scope narrowing: pptx / docx / pdf only).

Renders the exact same Recipe/Outline as DocumentDocxExportAdapter, as a
standalone PDF report instead of a .docx file. This is deliberately NOT
"convert the docx to PDF" — there is no docx-to-PDF conversion step
anywhere in this adapter, and no LibreOffice/soffice dependency. It
renders directly from the Recipe with reportlab, the same way every
other ExportPort implementation renders directly from the Recipe
(ADR-011: one generation, N independent export adapters — a broken/slow
adapter for one format never affects the others).

Content shape: PDF is a "document" format for content-shaping purposes,
not a "deck" or "visual" format — see json_pipeline_base.py's
export_format branch and quality_validator.py's document check, both of
which now treat "document_docx" and "document_pdf" identically (real
prose paragraphs, not slide-bullet fragments; see ADR-054 for why that
distinction exists at all). Only the rendering — this file — differs
between the two document formats; the content itself is identical
whichever one the user picks, exactly like docx and pptx share the
Recipe but never share the render.

Reuses document_docx_adapter's _all_read_as_prose test verbatim, rather
than importing it, to keep every ExportPort implementation a
self-contained adapter with no adapter-to-adapter import (matches the
existing project convention — pptx_adapter and document_docx_adapter
don't import each other either, they each import shared constants
from a lower layer, here _COLOR_SETS from pptx_adapter, which is the
one pre-existing exception to that rule and is left as-is rather than
introducing a second one for this small a piece of logic).
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.colors import Color
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
    PageBreak, HRFlowable,
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from backend.ports.export import ExportPort
from backend.models.recipe import Recipe, BlockType
from backend.adapters.export.pptx_adapter import _COLOR_SETS


def _hex(color: tuple[int, int, int]) -> Color:
    r, g, b = color
    return Color(r / 255, g / 255, b / 255)


class DocumentPdfExportAdapter(ExportPort):
    def format_id(self) -> str:
        return "document_pdf"

    def export(self, recipe: Recipe) -> bytes:
        import io

        colors = _COLOR_SETS.get(recipe.theme.color_set_id, _COLOR_SETS["neutral"])
        title_color = _hex(colors["title"])
        accent_color = _hex(colors["accent"])
        text_color = _hex(colors.get("text", colors["title"]))

        slides = sorted(recipe.outline.slides, key=lambda s: s.order)
        title_text = slides[0].title if slides else "Untitled Document"

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=LETTER,
            topMargin=1 * inch, bottomMargin=1 * inch,
            leftMargin=1 * inch, rightMargin=1 * inch,
        )

        heading_style = ParagraphStyle(
            "OpHeading", fontName="Helvetica-Bold", fontSize=16,
            textColor=title_color, spaceBefore=18, spaceAfter=10,
        )
        body_style = ParagraphStyle(
            "OpBody", fontName="Helvetica", fontSize=11,
            textColor=text_color, leading=16, spaceAfter=10,
        )
        bullet_style = ParagraphStyle(
            "OpBullet", fontName="Helvetica", fontSize=11,
            textColor=text_color, leading=15,
        )

        story = self._title_page(title_text, title_color, accent_color)

        # slides[0] became the title page above — same convention as
        # DocumentDocxExportAdapter, so the two document formats stay
        # structurally identical apart from the file format itself.
        for slide in slides[1:]:
            story.append(Paragraph(_escape(slide.title), heading_style))

            bullets = [b.text for b in slide.content_blocks if b.type == BlockType.BULLET and b.text]
            if self._all_read_as_prose(bullets):
                for paragraph_text in bullets:
                    story.append(Paragraph(_escape(paragraph_text), body_style))
            elif bullets:
                items = [ListItem(Paragraph(_escape(b), bullet_style), spaceAfter=4) for b in bullets]
                story.append(ListFlowable(items, bulletType="bullet", start="circle", leftIndent=18))
                story.append(Spacer(1, 10))

        doc.build(story)
        return buf.getvalue()

    @staticmethod
    def _all_read_as_prose(bullets: list[str]) -> bool:
        """Identical rule to DocumentDocxExportAdapter._all_read_as_prose
        — kept as a literal copy rather than a shared import, see module
        docstring for why. Any future change to this rule needs to be
        made in both places; that's an accepted, deliberate tradeoff for
        keeping each export adapter independently readable."""
        return len(bullets) >= 1 and all(b.rstrip().endswith((".", "!", "?")) for b in bullets)

    @staticmethod
    def _title_page(title: str, title_color: Color, accent_color: Color) -> list:
        title_style = ParagraphStyle(
            "OpTitle", fontName="Helvetica-Bold", fontSize=26,
            textColor=title_color, alignment=TA_CENTER, leading=32,
        )
        return [
            Spacer(1, 2.4 * inch),
            Paragraph(_escape(title), title_style),
            Spacer(1, 0.2 * inch),
            HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=0),
            PageBreak(),
        ]


def _escape(text: str) -> str:
    """reportlab's Paragraph treats its text as a tiny XML/markup
    dialect, not plain text — raw '&', '<', '>' from generated content
    would otherwise raise a parse error or silently corrupt the
    rendered page (the PDF equivalent of the document_docx title-anchor
    bug in ADR-054: a real, render-only bug that a passing test suite
    says nothing about unless the output is actually opened and read)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
