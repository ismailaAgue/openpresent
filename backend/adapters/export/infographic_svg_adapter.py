"""
InfographicSvgExportAdapter — ADR-046 (v3 Phase 6, first render target
beyond PPTX/DOCX).

Renders the exact same Recipe/Outline every other format consumes, as
a single vertically-scrolling SVG infographic: a title header followed
by numbered cards, one per section, each with a heading and its
bullets. This is deliberately the FIRST Phase 6 format built (per the
v3 roadmap's own sequencing: "diagrams and infographics first — pure
layout problems, no new content-generation logic") specifically
because it needs no new AI generation logic at all — same Strategy/
Outline/Content stages, same Outline model, only the export step
differs, exactly like ADR-041's document_docx adapter before it.

Reuses pptx_adapter.py's _COLOR_SETS rather than inventing a separate
infographic-only palette — the point of Theme.color_set_id existing
at all is that one theme choice should look consistent across every
format a project gets exported to, not just PPTX.

SVG text doesn't auto-wrap, so this does its own text wrapping via a
simple average-character-width estimate (textwrap.wrap against an
estimated max-chars-per-line) rather than pulling in a real font-
metrics library — an approximation, not exact per-glyph measurement,
which is a deliberate, stated tradeoff: exact wrapping would need
either a real font-rendering dependency or shipping actual font
metrics tables, disproportionate effort for what's meant to be a fast,
lightweight visual summary rather than a typography-precise document.
"""

import textwrap
from backend.ports.export import ExportPort
from backend.models.recipe import Recipe, BlockType
from backend.adapters.export.pptx_adapter import _COLOR_SETS
from backend.adapters.export.svg_utils import esc, hex_color, wrap_text

CANVAS_WIDTH = 900
MARGIN = 48
CARD_PADDING = 24
HEADER_TITLE_LINE_HEIGHT = 38
HEADER_BOTTOM_GAP = 32  # breathing room between the title and the first card
CARD_GAP = 20
NUMBER_CIRCLE_R = 18
TITLE_LINE_HEIGHT = 30
BULLET_LINE_HEIGHT = 24
CARD_TITLE_TO_BULLETS_GAP = 12
FOOTER_HEIGHT = 40  # ADR-054 — no longer a visible watermark, just reserved bottom breathing room
MAX_BULLETS_PER_CARD = 6  # an infographic card, not a full slide — stay skimmable

# Rough estimate: at 15px bullet-text size, an average character is
# ~8px wide in a standard sans font. Not exact glyph metrics (see
# module docstring) — good enough for wrapping decisions at this scale.
CHARS_PER_LINE = int((CANVAS_WIDTH - 2 * MARGIN - 2 * CARD_PADDING - 50) / 8)


def _esc(text: str) -> str:
    return esc(text)


def _hex(rgb: tuple[int, int, int]) -> str:
    return hex_color(rgb)


def _wrap(text: str, max_lines: int = 3) -> list[str]:
    return wrap_text(text, CHARS_PER_LINE, max_lines)


class InfographicSvgExportAdapter(ExportPort):
    def format_id(self) -> str:
        return "infographic_svg"

    def export(self, recipe: Recipe) -> bytes:
        colors = _COLOR_SETS.get(recipe.theme.color_set_id, _COLOR_SETS["neutral"])
        title_color = _hex(colors["title"])
        accent_color = _hex(colors["accent"])
        background_color = _hex(colors["background"])
        text_color = _hex(colors.get("text", colors["title"]))

        slides = sorted(recipe.outline.slides, key=lambda s: s.order)
        title = slides[0].title if slides else "Untitled"
        sections = slides[1:]  # slides[0] becomes the header, same convention as document_docx_adapter

        cards = []  # each: (height, svg_fragment_lines)
        for i, slide in enumerate(sections, start=1):
            bullets = [b.text for b in slide.content_blocks if b.type == BlockType.BULLET and b.text][:MAX_BULLETS_PER_CARD]
            title_lines = _wrap(slide.title, max_lines=2)
            bullet_line_groups = [_wrap(b, max_lines=2) for b in bullets]
            total_bullet_lines = sum(len(g) for g in bullet_line_groups)

            card_height = (
                CARD_PADDING * 2 + len(title_lines) * TITLE_LINE_HEIGHT
                + (CARD_TITLE_TO_BULLETS_GAP if bullets else 0)
                + total_bullet_lines * BULLET_LINE_HEIGHT
            )
            cards.append((card_height, i, title_lines, bullet_line_groups))

        header_title_lines = _wrap(title, max_lines=3)
        header_height = MARGIN + len(header_title_lines) * HEADER_TITLE_LINE_HEIGHT + HEADER_BOTTOM_GAP

        total_height = header_height + sum(h for h, *_ in cards) + CARD_GAP * max(len(cards) - 1, 0) + FOOTER_HEIGHT + MARGIN

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {total_height}" '
            f'width="{CANVAS_WIDTH}" height="{total_height}">',
            f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="{total_height}" fill="{background_color}"/>',
            f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="8" fill="{accent_color}"/>',
        ]

        # Header
        y = MARGIN + 36
        for line in header_title_lines:
            parts.append(
                f'<text x="{MARGIN}" y="{y}" font-family="sans-serif" font-size="30" '
                f'font-weight="700" fill="{title_color}">{_esc(line)}</text>'
            )
            y += HEADER_TITLE_LINE_HEIGHT

        cursor_y = header_height
        for card_height, num, title_lines, bullet_line_groups in cards:
            card_top = cursor_y
            parts.append(
                f'<rect x="{MARGIN}" y="{card_top}" width="{CANVAS_WIDTH - 2 * MARGIN}" '
                f'height="{card_height}" rx="10" fill="white" stroke="{accent_color}" stroke-opacity="0.25"/>'
            )
            circle_cx = MARGIN + CARD_PADDING + NUMBER_CIRCLE_R
            circle_cy = card_top + CARD_PADDING + NUMBER_CIRCLE_R
            parts.append(f'<circle cx="{circle_cx}" cy="{circle_cy}" r="{NUMBER_CIRCLE_R}" fill="{accent_color}"/>')
            parts.append(
                f'<text x="{circle_cx}" y="{circle_cy + 5}" font-family="sans-serif" font-size="16" '
                f'font-weight="700" fill="{background_color}" text-anchor="middle">{num}</text>'
            )

            text_x = MARGIN + CARD_PADDING + NUMBER_CIRCLE_R * 2 + 16
            ty = card_top + CARD_PADDING + 20
            for line in title_lines:
                parts.append(
                    f'<text x="{text_x}" y="{ty}" font-family="sans-serif" font-size="19" '
                    f'font-weight="600" fill="{title_color}">{_esc(line)}</text>'
                )
                ty += TITLE_LINE_HEIGHT

            if bullet_line_groups:
                ty += CARD_TITLE_TO_BULLETS_GAP - TITLE_LINE_HEIGHT + BULLET_LINE_HEIGHT - 6
                for group in bullet_line_groups:
                    for j, line in enumerate(group):
                        prefix = "• " if j == 0 else "  "
                        parts.append(
                            f'<text x="{text_x}" y="{ty}" font-family="sans-serif" font-size="15" '
                            f'fill="{text_color}">{_esc(prefix + line)}</text>'
                        )
                        ty += BULLET_LINE_HEIGHT

            cursor_y = card_top + card_height + CARD_GAP

        parts.append("</svg>")

        return "\n".join(parts).encode("utf-8")
