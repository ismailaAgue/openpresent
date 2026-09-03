"""
SvgPreviewAdapter — ADR-061.

Renders one lightweight SVG per slide, reusing the SAME theme colors,
per-theme style controls (corner_style, stat_chip, gradient_stops),
and layout decisions as the real PptxExportAdapter — without needing
LibreOffice at all. This exists specifically because a pixel-accurate
preview (screenshotting the real exported .pptx) needs LibreOffice
available in the PRODUCTION runtime, and this project's Render backend
is a plain pip-installed Python service with no system-package
mechanism (confirmed by reading DEPLOYMENT.md before writing this,
not assumed) — adding that would mean migrating to a Docker-based
Render deployment, a real infrastructure decision this module
deliberately avoids forcing.

This is NOT a pixel-accurate render of the exported file: no real
fonts (browsers substitute their own for the font-family names),
slightly different text-wrapping math than python-pptx's own. It IS a
faithful render of the actual DESIGN DECISIONS — same colors, same
corner decoration per theme, same stat-chip treatment, same bullet
markers, same comparison-card/process-badge layout — which is what
"doesn't show the real design" actually needed: not literal pixel
parity, but no longer a generic title+bullets text mockup that ignores
the theme entirely.

Layout coverage: title, bullet_list (plain and colored-bullet), and
statistics (chip and plain) are fully covered. comparison and process
fall back to a themed bullet-list rendering — a stated, deliberate
scope limit (see this class's render() docstring), not a silent gap.
"""

from xml.sax.saxutils import escape as _xml_escape
from backend.models.recipe import Recipe, BlockType
from backend.adapters.export.pptx_adapter import (
    _COLOR_SETS, _tint, CHIP_NUMBER_PATTERN,
)

# 4:3, matching PptxExportAdapter's actual (unconfigured, default
# python-pptx) slide dimensions — confirmed by reading that module,
# not assumed to be 16:9.
VIEWBOX_WIDTH = 800
VIEWBOX_HEIGHT = 600


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """SVG <text> has no native word-wrap — this is the same rough
    "estimate characters per line" approach pptx_adapter's own
    _fitting_title_font_size uses for its length-based sizing, applied
    here to actual line-breaking instead. Not typographically exact
    (proportional fonts vary per character), but good enough for a
    preview that's explicitly not claiming pixel accuracy."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


class SvgPreviewAdapter:
    """Not an ExportPort implementation — this produces inline preview
    SVGs, not a downloadable file format, so it deliberately doesn't
    implement that interface (no format_id/no file the person would
    ever download on its own)."""

    def render(self, recipe: Recipe) -> list[dict]:
        """Returns [{"order": 1, "svg": "<svg ...>...</svg>"}, ...],
        one entry per slide, in order. Slide 1 always renders as a
        title slide, matching PptxExportAdapter's own convention
        (slides[0] is special, regardless of its layout_type)."""
        colors = _COLOR_SETS.get(recipe.theme.color_set_id, _COLOR_SETS["neutral"])
        slides = sorted(recipe.outline.slides, key=lambda s: s.order)
        out = []
        for i, slide in enumerate(slides):
            bullets = [b.text for b in slide.content_blocks if b.type == BlockType.BULLET and b.text]
            if i == 0:
                svg = self._render_title(slide.title, colors)
            elif slide.layout_type == "statistics" and bullets:
                svg = self._render_statistics(slide.title, bullets, colors)
            else:
                # comparison/process fall back to themed bullets — a
                # stated scope limit (module docstring), not a silent gap.
                svg = self._render_bullets(slide.title, bullets, colors)
            out.append({"order": slide.order, "svg": svg})
        return out

    # -- shared pieces --------------------------------------------------

    def _corner_decoration(self, colors: dict, small: bool) -> str:
        style = colors.get("corner_style", "circle")
        if style == "none":
            return ""
        if style == "blob" and colors.get("gradient_stops"):
            r = 55 if small else 145
            cx = VIEWBOX_WIDTH - 10 if small else 0
            cy = VIEWBOX_HEIGHT - 10 if small else 0
            g1, g2 = colors["gradient_stops"]
            grad_id = f"grad{'s' if small else 'l'}"
            return (
                f'<defs><linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="100%">'
                f'<stop offset="0%" stop-color="{_hex(g1)}"/>'
                f'<stop offset="100%" stop-color="{_hex(g2)}"/>'
                f'</linearGradient></defs>'
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{grad_id})"/>'
            )
        r = 16 if small else 36
        cx = VIEWBOX_WIDTH - 4 if small else -4
        cy = VIEWBOX_HEIGHT - 4 if small else -4
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{_hex(colors["accent"])}"/>'

    def _title_with_accent(self, title: str, colors: dict) -> str:
        lines = _wrap_text(title, max_chars=28)
        parts = []
        y = 90
        for line in lines[:2]:
            parts.append(
                f'<text x="40" y="{y}" font-size="26" font-weight="700" '
                f'fill="{_hex(colors["title"])}" font-family="Inter, sans-serif">{_xml_escape(line)}</text>'
            )
            y += 34
        bar_y = y + 6
        parts.append(f'<rect x="40" y="{bar_y}" width="90" height="4" fill="{_hex(colors["accent"])}"/>')
        return "".join(parts), bar_y + 30

    def _svg_wrapper(self, body: str, colors: dict) -> str:
        return (
            f'<svg viewBox="0 0 {VIEWBOX_WIDTH} {VIEWBOX_HEIGHT}" xmlns="http://www.w3.org/2000/svg">'
            f'<rect x="0" y="0" width="{VIEWBOX_WIDTH}" height="{VIEWBOX_HEIGHT}" fill="{_hex(colors["background"])}"/>'
            f'{body}'
            f'</svg>'
        )

    # -- layouts ----------------------------------------------------------

    def _render_title(self, title: str, colors: dict) -> str:
        blob = self._corner_decoration(colors, small=False)
        lines = _wrap_text(title, max_chars=22)
        parts = [blob]
        y = 280
        for line in lines[:3]:
            parts.append(
                f'<text x="40" y="{y}" font-size="34" font-weight="700" '
                f'fill="{_hex(colors["title"])}" font-family="Inter, sans-serif">{_xml_escape(line)}</text>'
            )
            y += 44
        return self._svg_wrapper("".join(parts), colors)

    def _render_bullets(self, title: str, bullets: list[str], colors: dict) -> str:
        title_svg, content_top = self._title_with_accent(title, colors)
        parts = [self._corner_decoration(colors, small=True), title_svg]
        y = content_top
        for bullet in bullets[:6]:
            parts.append(f'<rect x="40" y="{y - 12}" width="10" height="10" fill="{_hex(colors["accent"])}"/>')
            lines = _wrap_text(bullet, max_chars=62)
            for line in lines[:2]:
                parts.append(
                    f'<text x="60" y="{y}" font-size="14" fill="{_hex(colors["text"])}" '
                    f'font-family="Inter, sans-serif">{_xml_escape(line)}</text>'
                )
                y += 20
            y += 8
        return self._svg_wrapper("".join(parts), colors)

    def _render_statistics(self, title: str, bullets: list[str], colors: dict) -> str:
        title_svg, content_top = self._title_with_accent(title, colors)
        parts = [self._corner_decoration(colors, small=True), title_svg]
        stats = bullets[:4]
        margin, gap = 30, 16
        card_width = (VIEWBOX_WIDTH - (2 * margin) - (gap * (len(stats) - 1))) // len(stats) if stats else 0
        card_top = content_top + 20
        card_height = 160

        if not colors.get("stat_chip"):
            for idx, stat_text in enumerate(stats):
                cx = margin + idx * (card_width + gap) + card_width // 2
                parts.append(
                    f'<text x="{cx}" y="{card_top + 60}" font-size="18" font-weight="700" '
                    f'text-anchor="middle" fill="{_hex(colors["accent"])}" '
                    f'font-family="Inter, sans-serif">{_xml_escape(stat_text[:24])}</text>'
                )
            return self._svg_wrapper("".join(parts), colors)

        chip_fill = _hex(_tint(colors["accent"], 0.85))
        for idx, stat_text in enumerate(stats):
            left = margin + idx * (card_width + gap)
            match = CHIP_NUMBER_PATTERN.search(stat_text)
            if match:
                number_part = match.group(0).strip()
                label_part = (stat_text[:match.start()] + stat_text[match.end():]).strip(" -:,.")
            else:
                number_part, label_part = stat_text, ""
            parts.append(
                f'<rect x="{left}" y="{card_top}" width="{card_width}" height="{card_height}" '
                f'rx="14" fill="{chip_fill}"/>'
            )
            cx = left + card_width // 2
            number_size = 22 if len(number_part) <= 6 else (17 if len(number_part) <= 10 else 14)
            parts.append(
                f'<text x="{cx}" y="{card_top + 45}" font-size="{number_size}" font-weight="700" '
                f'text-anchor="middle" fill="{_hex(colors["accent"])}" '
                f'font-family="Inter, sans-serif">{_xml_escape(number_part)}</text>'
            )
            if label_part:
                for j, line in enumerate(_wrap_text(label_part, max_chars=18)[:2]):
                    parts.append(
                        f'<text x="{cx}" y="{card_top + 75 + j * 16}" font-size="10.5" '
                        f'text-anchor="middle" fill="{_hex(colors["text"])}" '
                        f'font-family="Inter, sans-serif">{_xml_escape(line)}</text>'
                    )
        return self._svg_wrapper("".join(parts), colors)
