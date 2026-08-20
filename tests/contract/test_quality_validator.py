from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.validation.quality_validator import validate_and_fix, MAX_BULLETS_PER_SLIDE


def bullet(text):
    return ContentBlock(type=BlockType.BULLET, text=text)


def note(text):
    return ContentBlock(type=BlockType.NOTE, text=text)


def make_outline(slides):
    return Outline(structure_source=StructureSource.AI_GENERATED, slides=slides)


def test_flags_duplicate_titles():
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a")]),
        Slide(order=2, title="Intro", content_blocks=[bullet("b")]),
        Slide(order=3, title="Thank You", content_blocks=[bullet("Questions?")]),
    ])
    _, report = validate_and_fix(outline)
    assert any("Duplicate" in i for i in report.issues)


def test_flags_empty_slide():
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a")]),
        Slide(order=2, title="Empty", content_blocks=[]),
        Slide(order=3, title="Thank You", content_blocks=[bullet("Questions?")]),
    ])
    _, report = validate_and_fix(outline)
    assert any("no content" in i for i in report.issues)


def test_trims_excessive_bullets():
    too_many = [bullet(f"point {i}") for i in range(MAX_BULLETS_PER_SLIDE + 5)]
    outline = make_outline([
        Slide(order=1, title="Overloaded", content_blocks=too_many),
    ])
    fixed, report = validate_and_fix(outline)
    remaining = [b for b in fixed.slides[0].content_blocks if b.type == BlockType.BULLET]
    assert len(remaining) == MAX_BULLETS_PER_SLIDE
    assert any("Trimmed" in f for f in report.auto_fixed)


def test_dedupes_repeated_bullets_across_slides():
    outline = make_outline([
        Slide(order=1, title="A", content_blocks=[bullet("Same point")]),
        Slide(order=2, title="B", content_blocks=[bullet("Same point"), bullet("Unique point")]),
    ])
    fixed, report = validate_and_fix(outline)
    slide_b_texts = [b.text for b in fixed.slides[1].content_blocks]
    assert "Same point" not in slide_b_texts
    assert "Unique point" in slide_b_texts
    assert any("repeated" in f for f in report.auto_fixed)


def test_adds_closing_slide_when_missing():
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a")]),
        Slide(order=2, title="Details", content_blocks=[bullet("b")]),
    ])
    fixed, report = validate_and_fix(outline)
    assert fixed.slides[-1].title == "Thank You"
    assert any("closing slide" in f for f in report.auto_fixed)


def test_does_not_duplicate_closing_slide_when_already_present():
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a")]),
        Slide(order=2, title="Summary", content_blocks=[bullet("b")]),
    ])
    fixed, report = validate_and_fix(outline)
    assert len(fixed.slides) == 2
    assert not any("closing slide" in f for f in report.auto_fixed)


def test_clean_outline_has_no_issues_and_high_score():
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a"), note("n")]),
        Slide(order=2, title="Body", content_blocks=[bullet("b"), bullet("c"), note("n")]),
        Slide(order=3, title="Thank You", content_blocks=[bullet("Questions?")]),
    ])
    _, report = validate_and_fix(outline)
    assert report.issues == []
    assert report.score >= 8.0
