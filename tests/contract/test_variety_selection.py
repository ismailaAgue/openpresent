"""
Presentation variety — ADR-030 (narrative style / theme variant
selection), ADR-073 (theme selection is now editorial_cream only,
superseding ADR-071's 75/25 weighting).
"""

from backend.pipeline.variety import pick_theme_variant, suggest_style, THEME_VARIANT_IDS, NARRATIVE_STYLES


def test_suggest_style_always_returns_a_known_narrative_style():
    ids = {s["id"] for s in NARRATIVE_STYLES}
    for _ in range(20):
        assert suggest_style()["id"] in ids


def test_pick_theme_variant_always_returns_a_known_theme_id():
    for _ in range(50):
        assert pick_theme_variant() in THEME_VARIANT_IDS


def test_pick_theme_variant_always_returns_editorial_cream():
    """ADR-073 — "editorial cream only, remove the other themes" is an
    explicit, direct instruction, not a weighting. No more randomness
    at all: every single call returns "editorial_cream", full stop.
    This supersedes ADR-071's 75/25 weighted pick entirely."""
    draws = {pick_theme_variant() for _ in range(200)}
    assert draws == {"editorial_cream"}, f"expected only editorial_cream, got {draws}"
