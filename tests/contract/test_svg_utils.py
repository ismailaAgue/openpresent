"""Contract tests for svg_utils.py — the shared helpers extracted for
infographic_svg_adapter.py and diagram_svg_adapter.py (ADR-047)."""

from backend.adapters.export.svg_utils import esc, hex_color, wrap_text


def test_esc_escapes_all_five_xml_special_characters():
    assert esc("R&D <Report> \"Final\"") == "R&amp;D &lt;Report&gt; &quot;Final&quot;"


def test_esc_leaves_plain_text_unchanged():
    assert esc("Nothing special here") == "Nothing special here"


def test_hex_color_formats_rgb_tuple():
    assert hex_color((0x1B, 0x3A, 0x5C)) == "#1b3a5c"


def test_hex_color_pads_single_digit_components():
    assert hex_color((0, 5, 255)) == "#0005ff"


def test_wrap_text_short_text_stays_one_line():
    assert wrap_text("Short title", chars_per_line=40, max_lines=3) == ["Short title"]


def test_wrap_text_splits_long_text_across_lines():
    lines = wrap_text("This is a much longer piece of text that needs wrapping", chars_per_line=20, max_lines=5)
    assert len(lines) > 1
    assert all(len(line) <= 20 or " " not in line for line in lines)  # unbreakable long tokens excepted


def test_wrap_text_truncates_with_ellipsis_beyond_max_lines():
    long_text = " ".join(["word"] * 50)
    lines = wrap_text(long_text, chars_per_line=10, max_lines=2)
    assert len(lines) == 2
    assert lines[-1].endswith("…")


def test_wrap_text_empty_string_returns_one_empty_line_not_raise():
    assert wrap_text("", chars_per_line=20, max_lines=3) == [""]
