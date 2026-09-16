"""
Presentation variety — ADR-030 (narrative style / theme variant
selection), ADR-071 (theme selection reweighted toward editorial_cream).
"""

from backend.pipeline.variety import pick_theme_variant, suggest_style, THEME_VARIANT_IDS, NARRATIVE_STYLES


def test_suggest_style_always_returns_a_known_narrative_style():
    ids = {s["id"] for s in NARRATIVE_STYLES}
    for _ in range(20):
        assert suggest_style()["id"] in ids


def test_pick_theme_variant_always_returns_a_known_theme_id():
    for _ in range(50):
        assert pick_theme_variant() in THEME_VARIANT_IDS


def test_pick_theme_variant_is_weighted_heavily_toward_editorial_cream():
    """ADR-071 — editorial_cream must be the clear majority pick, not
    a flat 1-in-9 chance the way it (and every other theme) used to
    be. Statistical, not exact-count, assertion — genuinely random —
    but 1000 draws at a real 75% weight landing below 60% has
    astronomically low odds of happening by chance; this is checking
    the actual behavior, not a hardcoded mock of it."""
    draws = [pick_theme_variant() for _ in range(1000)]
    editorial_share = draws.count("editorial_cream") / len(draws)
    assert editorial_share > 0.60, f"editorial_cream was only picked {editorial_share:.0%} of the time"


def test_pick_theme_variant_can_still_pick_other_themes():
    """The other 8 themes must remain genuinely reachable — ADR-071
    was a reweighting, not a removal. All 1000 draws landing on
    editorial_cream alone would mean the "or random.choice(...)"
    branch is unreachable (a real bug, not just bad luck)."""
    draws = {pick_theme_variant() for _ in range(1000)}
    assert len(draws) > 1, "only editorial_cream was ever picked across 1000 draws"
    non_editorial = [v for v in THEME_VARIANT_IDS if v != "editorial_cream"]
    assert any(v in draws for v in non_editorial)
