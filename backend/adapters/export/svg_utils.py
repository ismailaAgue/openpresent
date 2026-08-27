"""
Shared SVG helpers — extracted from infographic_svg_adapter.py
(ADR-046) when diagram_svg_adapter.py (ADR-047) needed the identical
escaping/color/wrapping logic. Deliberately just pure, stateless
utility functions, not a shared base class or shared layout engine —
per ExportPort's own docstring ("a broken/slow adapter for one format
never affects the others"), each SVG adapter still owns its entire
layout algorithm independently. Sharing pure string-manipulation
helpers doesn't create the coupling that principle is actually
guarding against; duplicating character-escaping logic across every
future SVG adapter would just be a latent bug waiting to diverge.
"""

import textwrap


def esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def hex_color(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def wrap_text(text: str, chars_per_line: int, max_lines: int = 3) -> list[str]:
    """SVG text doesn't auto-wrap, so every SVG adapter needs this.
    Uses a simple average-character-width estimate via textwrap.wrap,
    not real per-glyph font metrics — an approximation, not exact
    measurement (see infographic_svg_adapter.py's module docstring for
    the full reasoning on why that's a deliberate, stated tradeoff)."""
    lines = textwrap.wrap(text, width=max(chars_per_line, 20)) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip()[: max(chars_per_line - 1, 10)] + "…"
    return lines
