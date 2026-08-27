"""
DiagramSvgExportAdapter — ADR-047 (v3 Phase 6, second render target).

Renders the same Recipe/Outline every format consumes as a top-to-
bottom process-flow diagram: one box per section, connected by
arrows in slide order. This is deliberately a PROCESS/SEQUENCE
diagram, not a general flowchart with branching or decisions — the
Outline model's Slides are a flat, ordered list (see models/recipe.py),
which maps naturally onto "step 1 leads to step 2 leads to step 3"
but has no representation of a decision point, a loop, or parallel
branches. Building a diagram type the data model can't actually
describe would mean either silently ignoring structure the model
doesn't have (dishonest — it would look like a real flowchart while
being incapable of encoding one) or inventing a new structured
branching input the AI pipeline doesn't populate (real, but a
materially bigger change than this pass is — deferred, not done here,
see V3_ROADMAP.md). A linear process flow is the honest diagram this
data model actually supports today.

Each box shows the section's title and, space permitting, its first
bullet as a terse sub-line (not a card of many bullets like the
infographic adapter's cards — a diagram box should read in a glance,
not be read like a document). Shares esc/hex_color/wrap_text with
infographic_svg_adapter.py via svg_utils.py rather than duplicating
that logic a second time.
"""

from backend.ports.export import ExportPort
from backend.models.recipe import Recipe, BlockType
from backend.adapters.export.pptx_adapter import _COLOR_SETS
from backend.adapters.export.svg_utils import esc, hex_color, wrap_text

CANVAS_WIDTH = 700
MARGIN = 48
BOX_PADDING = 20
BOX_WIDTH = CANVAS_WIDTH - 2 * MARGIN
TITLE_LINE_HEIGHT = 26
SUBLINE_LINE_HEIGHT = 20
TITLE_TO_SUBLINE_GAP = 8
ARROW_LENGTH = 44  # vertical gap between boxes, filled by the connecting arrow
HEADER_TITLE_LINE_HEIGHT = 36
HEADER_BOTTOM_GAP = 28
FOOTER_HEIGHT = 36
MAX_SUBLINE_LINES = 2

CHARS_PER_LINE_TITLE = int((BOX_WIDTH - 2 * BOX_PADDING) / 9)   # 17px bold text
CHARS_PER_LINE_SUB = int((BOX_WIDTH - 2 * BOX_PADDING) / 7.2)   # 13px regular text
CHARS_PER_LINE_HEADER = int((CANVAS_WIDTH - 2 * MARGIN) / 15)   # 26px bold header text


class DiagramSvgExportAdapter(ExportPort):
    def format_id(self) -> str:
        return "diagram_svg"

    def export(self, recipe: Recipe) -> bytes:
        colors = _COLOR_SETS.get(recipe.theme.color_set_id, _COLOR_SETS["neutral"])
        title_color = hex_color(colors["title"])
        accent_color = hex_color(colors["accent"])
        background_color = hex_color(colors["background"])
        text_color = hex_color(colors.get("text", colors["title"]))

        slides = sorted(recipe.outline.slides, key=lambda s: s.order)
        title = slides[0].title if slides else "Untitled"
        steps = slides[1:]  # slides[0] becomes the header, same convention as the other SVG/document adapters

        boxes = []  # each: (height, title_lines, subline_lines)
        for slide in steps:
            title_lines = wrap_text(slide.title, CHARS_PER_LINE_TITLE, max_lines=2)
            first_bullet = next(
                (b.text for b in slide.content_blocks if b.type == BlockType.BULLET and b.text), None
            )
            subline_lines = wrap_text(first_bullet, CHARS_PER_LINE_SUB, MAX_SUBLINE_LINES) if first_bullet else []

            box_height = (
                BOX_PADDING * 2 + len(title_lines) * TITLE_LINE_HEIGHT
                + (TITLE_TO_SUBLINE_GAP + len(subline_lines) * SUBLINE_LINE_HEIGHT if subline_lines else 0)
            )
            boxes.append((box_height, title_lines, subline_lines))

        header_title_lines = wrap_text(title, CHARS_PER_LINE_HEADER, max_lines=2)
        header_height = MARGIN + len(header_title_lines) * HEADER_TITLE_LINE_HEIGHT + HEADER_BOTTOM_GAP

        total_boxes_height = sum(h for h, *_ in boxes)
        total_arrows_height = ARROW_LENGTH * max(len(boxes) - 1, 0)
        total_height = header_height + total_boxes_height + total_arrows_height + FOOTER_HEIGHT + MARGIN

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {total_height}" '
            f'width="{CANVAS_WIDTH}" height="{total_height}">',
            f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="{total_height}" fill="{background_color}"/>',
            f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="8" fill="{accent_color}"/>',
            # Arrowhead marker, referenced by every connector below.
            "<defs><marker id=\"arrowhead\" markerWidth=\"10\" markerHeight=\"8\" refX=\"8\" refY=\"4\" "
            f'orient="auto"><polygon points="0 0, 10 4, 0 8" fill="{accent_color}"/></marker></defs>',
        ]

        y = MARGIN + 30
        for line in header_title_lines:
            parts.append(
                f'<text x="{MARGIN}" y="{y}" font-family="sans-serif" font-size="26" '
                f'font-weight="700" fill="{title_color}">{esc(line)}</text>'
            )
            y += HEADER_TITLE_LINE_HEIGHT

        cursor_y = header_height
        box_x = MARGIN
        for i, (box_height, title_lines, subline_lines) in enumerate(boxes):
            if i > 0:
                # Connector arrow from the bottom of the previous box to the top of this one.
                arrow_x = box_x + BOX_WIDTH / 2
                arrow_top = cursor_y - ARROW_LENGTH + 4
                arrow_bottom = cursor_y - 6
                parts.append(
                    f'<line x1="{arrow_x}" y1="{arrow_top}" x2="{arrow_x}" y2="{arrow_bottom}" '
                    f'stroke="{accent_color}" stroke-width="2.5" marker-end="url(#arrowhead)"/>'
                )

            parts.append(
                f'<rect x="{box_x}" y="{cursor_y}" width="{BOX_WIDTH}" height="{box_height}" '
                f'rx="10" fill="white" stroke="{accent_color}" stroke-width="1.5"/>'
            )
            ty = cursor_y + BOX_PADDING + 18
            for line in title_lines:
                parts.append(
                    f'<text x="{box_x + BOX_WIDTH / 2}" y="{ty}" font-family="sans-serif" font-size="17" '
                    f'font-weight="700" fill="{title_color}" text-anchor="middle">{esc(line)}</text>'
                )
                ty += TITLE_LINE_HEIGHT
            if subline_lines:
                ty += TITLE_TO_SUBLINE_GAP - TITLE_LINE_HEIGHT + SUBLINE_LINE_HEIGHT - 4
                for line in subline_lines:
                    parts.append(
                        f'<text x="{box_x + BOX_WIDTH / 2}" y="{ty}" font-family="sans-serif" font-size="13" '
                        f'fill="{text_color}" text-anchor="middle">{esc(line)}</text>'
                    )
                    ty += SUBLINE_LINE_HEIGHT

            cursor_y += box_height + ARROW_LENGTH

        parts.append(
            f'<text x="{MARGIN}" y="{total_height - MARGIN + 8}" font-family="sans-serif" '
            f'font-size="11" fill="{text_color}" fill-opacity="0.6">Generated with OpenPresent</text>'
        )
        parts.append("</svg>")

        return "\n".join(parts).encode("utf-8")
