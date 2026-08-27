"""
PosterSvgExportAdapter — ADR-048 (v3 Phase 6, third and final render
target: posters and social graphics).

Renders the same Recipe/Outline every format consumes as a single
portrait-orientation graphic (800x1000, close to a common social/print
poster ratio) — a hero headline with a small number of punchy
highlight lines beneath it, NOT a numbered list or a card stack like
the infographic/diagram adapters before it.

This is a deliberately different visual language from those two, for
a reason stated in the v3 roadmap itself: posters need real design
judgment, not another layout algorithm applied to the same card/box
pattern. Two structural choices follow directly from that, both
informed by this project's frontend-design skill even though this is
a generation ENGINE (one template serving arbitrary topics) rather
than a bespoke single build (the skill's usual context) — applied at
the template-design level instead:

1. NO numbered markers. The infographic and diagram adapters both use
   numbered circles because their content genuinely IS a sequence (a
   deck's slide order, a process's steps). A poster's highlight lines
   are NOT a sequence — they're independently true claims about the
   same topic — so numbering them would be exactly the kind of
   decoration-that-doesn't-encode-real-information the skill calls
   out as a templated default to avoid. A small accent tick precedes
   each line instead, doing zero sequence-implying work.
2. The headline dominates. Where the other two adapters give the
   title a modest header treatment and spend most of the canvas on
   content, this adapter's hero title is the largest, boldest element
   on the page — "the hero is a thesis," per the skill — with a
   restrained accent-circle signature device behind it for visual
   identity, not decoration for its own sake.

Where this does NOT follow the skill as literally as a bespoke page
would: color palette. The skill's guidance is to pick one considered,
specific palette per brief. This adapter instead reuses the same
_COLOR_SETS every other export format already uses (same reasoning as
ADR-046/047) — because this is a reusable engine serving arbitrary
topics and brand profiles, not a one-off page, consistency of a
user's chosen theme ACROSS every format they export to matters more
here than a bespoke one-off palette would. Stated explicitly as a
deliberate tension with the skill's usual guidance, not an oversight.
"""

from backend.ports.export import ExportPort
from backend.models.recipe import Recipe, BlockType
from backend.adapters.export.pptx_adapter import _COLOR_SETS
from backend.adapters.export.svg_utils import esc, hex_color, wrap_text

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 1000
MARGIN = 64
HEADLINE_LINE_HEIGHT = 62
HEADLINE_FONT_SIZE = 52
DIVIDER_GAP_ABOVE = 36
DIVIDER_WIDTH = 90
HIGHLIGHT_LINE_HEIGHT = 34
HIGHLIGHT_FONT_SIZE = 21
HIGHLIGHT_TICK_SIZE = 10
HIGHLIGHT_TICK_GAP = 16
MAX_HIGHLIGHTS = 4  # a poster has room for a handful of claims, not a list
FOOTER_HEIGHT = 44

CHARS_PER_LINE_HEADLINE = int((CANVAS_WIDTH - 2 * MARGIN) / 26)  # large bold text, wide average glyph
CHARS_PER_LINE_HIGHLIGHT = int((CANVAS_WIDTH - 2 * MARGIN - HIGHLIGHT_TICK_SIZE - HIGHLIGHT_TICK_GAP) / 11)


class PosterSvgExportAdapter(ExportPort):
    def format_id(self) -> str:
        return "poster_svg"

    def export(self, recipe: Recipe) -> bytes:
        colors = _COLOR_SETS.get(recipe.theme.color_set_id, _COLOR_SETS["neutral"])
        title_color = hex_color(colors["title"])
        accent_color = hex_color(colors["accent"])
        background_color = hex_color(colors["background"])
        text_color = hex_color(colors.get("text", colors["title"]))

        slides = sorted(recipe.outline.slides, key=lambda s: s.order)
        title = slides[0].title if slides else "Untitled"
        sections = slides[1:]

        # One highlight per section: its first bullet if it has one,
        # else the section's own title — a poster can't afford an
        # empty highlight line just because a section happened to have
        # no bullets, and the section title is still a true claim
        # about the topic even without supporting detail beneath it.
        highlights = []
        for slide in sections:
            first_bullet = next(
                (b.text for b in slide.content_blocks if b.type == BlockType.BULLET and b.text), None
            )
            highlights.append(first_bullet or slide.title)
        highlights = highlights[:MAX_HIGHLIGHTS]

        headline_lines = wrap_text(title, CHARS_PER_LINE_HEADLINE, max_lines=4)
        highlight_line_groups = [wrap_text(h, CHARS_PER_LINE_HIGHLIGHT, max_lines=2) for h in highlights]

        # Compute the whole content block's height FIRST so it can be
        # vertically centered in the fixed canvas rather than always
        # starting at a fixed y — with few highlights that fixed-start
        # approach left the entire bottom half of the poster empty,
        # which reads as broken, not minimal (caught by rendering a
        # realistic sample before writing any tests, same discipline
        # ADR-046/047 established).
        headline_block_height = len(headline_lines) * HEADLINE_LINE_HEIGHT
        highlights_block_height = sum(
            len(group) * HIGHLIGHT_LINE_HEIGHT + HIGHLIGHT_TICK_GAP + 10 for group in highlight_line_groups
        )
        divider_space = (DIVIDER_GAP_ABOVE + 30) if highlight_line_groups else 0
        content_height = headline_block_height + divider_space + highlights_block_height
        # Never start higher than clear of the signature circles, never
        # lower than leaves room for the footer — centering within that
        # safe band, not the full canvas.
        safe_top, safe_bottom = 190, CANVAS_HEIGHT - FOOTER_HEIGHT - MARGIN
        start_y = max(safe_top, safe_top + (safe_bottom - safe_top - content_height) / 2)

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_WIDTH} {CANVAS_HEIGHT}" '
            f'width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}">',
            f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="{CANVAS_HEIGHT}" fill="{background_color}"/>',
        ]

        # Signature device: two overlapping accent circles bleeding off
        # the top-right corner, low-opacity so they read as texture
        # behind the headline rather than competing with it. This is
        # the one deliberate visual risk this template takes, per the
        # skill's "spend your boldness in one place" — everything else
        # here is quiet on purpose.
        parts.append(f'<circle cx="{CANVAS_WIDTH - 60}" cy="120" r="220" fill="{accent_color}" fill-opacity="0.12"/>')
        parts.append(f'<circle cx="{CANVAS_WIDTH - 140}" cy="60" r="120" fill="{accent_color}" fill-opacity="0.18"/>')
        parts.append(f'<rect x="0" y="0" width="{CANVAS_WIDTH}" height="6" fill="{accent_color}"/>')

        # Hero headline
        y = start_y + HEADLINE_FONT_SIZE * 0.8
        for line in headline_lines:
            parts.append(
                f'<text x="{CANVAS_WIDTH / 2}" y="{y}" font-family="sans-serif" font-size="{HEADLINE_FONT_SIZE}" '
                f'font-weight="800" fill="{title_color}" text-anchor="middle">{esc(line)}</text>'
            )
            y += HEADLINE_LINE_HEIGHT

        # Divider — a real structural device marking "supporting claims
        # start here," not decoration; short and centered rather than
        # full-width, so it reads as a considered mark, not a rule.
        # Only rendered when there's actually something for it to
        # introduce — an orphaned divider pointing at zero highlights
        # would be exactly the unjustified decoration the skill warns
        # against, not real structure.
        divider_y = start_y + headline_block_height + DIVIDER_GAP_ABOVE - HEADLINE_LINE_HEIGHT + HEADLINE_FONT_SIZE * 0.8
        if highlight_line_groups:
            parts.append(
                f'<line x1="{CANVAS_WIDTH / 2 - DIVIDER_WIDTH / 2}" y1="{divider_y}" '
                f'x2="{CANVAS_WIDTH / 2 + DIVIDER_WIDTH / 2}" y2="{divider_y}" '
                f'stroke="{accent_color}" stroke-width="3"/>'
            )

        hy = divider_y + 46
        for group in highlight_line_groups:
            # A small centered accent square marks each highlight,
            # placed ABOVE its text rather than beside it — beside-text
            # placement needs accurate text-width measurement to align
            # correctly (this project's wrap_text is a character-count
            # estimate, not real font metrics, per svg_utils.py's own
            # documented limitation), and got it visibly wrong the
            # first pass (the tick overlapped the text). A centered
            # mark above the block sidesteps needing that measurement
            # at all — it's already correctly centered by construction.
            parts.append(
                f'<rect x="{CANVAS_WIDTH / 2 - HIGHLIGHT_TICK_SIZE / 2}" y="{hy - HIGHLIGHT_LINE_HEIGHT + 6}" '
                f'width="{HIGHLIGHT_TICK_SIZE}" height="4" fill="{accent_color}"/>'
            )
            hy += HIGHLIGHT_TICK_GAP
            for line in group:
                parts.append(
                    f'<text x="{CANVAS_WIDTH / 2}" y="{hy}" font-family="sans-serif" '
                    f'font-size="{HIGHLIGHT_FONT_SIZE}" fill="{text_color}" '
                    f'text-anchor="middle">{esc(line)}</text>'
                )
                hy += HIGHLIGHT_LINE_HEIGHT
            hy += 10  # extra breathing room between distinct highlights

        parts.append(f'<rect x="0" y="{CANVAS_HEIGHT - 6}" width="{CANVAS_WIDTH}" height="6" fill="{accent_color}"/>')
        parts.append(
            f'<text x="{CANVAS_WIDTH / 2}" y="{CANVAS_HEIGHT - MARGIN + 16}" font-family="sans-serif" '
            f'font-size="12" fill="{text_color}" fill-opacity="0.55" text-anchor="middle">'
            f"Generated with OpenPresent</text>"
        )
        parts.append("</svg>")

        return "\n".join(parts).encode("utf-8")
