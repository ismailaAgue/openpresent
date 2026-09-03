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


def test_closing_slide_is_localized_when_language_is_set():
    """ADR-060 — a deck generated in French previously still got an
    English 'Thank You' slide appended regardless, since this function
    had no language awareness at all."""
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a")]),
        Slide(order=2, title="Details", content_blocks=[bullet("b")]),
    ])
    fixed, report = validate_and_fix(outline, language="fr")
    assert fixed.slides[-1].title == "Merci"
    assert fixed.slides[-1].content_blocks[0].text == "Des questions ?"


def test_closing_slide_language_lookup_is_case_insensitive_and_accepts_full_names():
    outline = make_outline([Slide(order=1, title="Intro", content_blocks=[bullet("a")])])
    fixed, _ = validate_and_fix(outline, language="Spanish")
    assert fixed.slides[-1].title == "Gracias"


def test_closing_slide_falls_back_to_english_for_an_unsupported_language():
    """A real, stated limitation (see CLOSING_SLIDE_TEXT's own comment)
    — not every language is covered, and falling back to English
    honestly is better than silently mistranslating."""
    outline = make_outline([Slide(order=1, title="Intro", content_blocks=[bullet("a")])])
    fixed, _ = validate_and_fix(outline, language="Klingon")
    assert fixed.slides[-1].title == "Thank You"


def test_closing_slide_detection_recognizes_non_english_hints_too():
    """A French AI-generated closing slide must not get a second,
    redundant English one appended on top of it."""
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[bullet("a")]),
        Slide(order=2, title="Merci", content_blocks=[bullet("Des questions ?")]),
    ])
    fixed, report = validate_and_fix(outline, language="fr")
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


# -- Format-aware validation (ADR-054) --------------------------------------
# "Paragraph-length bullet" and "layout overflow risk" are deck-specific
# defects — a slide bullet SHOULD be short, a scrolling Word document has
# no fixed layout region to overflow. Flagging either for document_docx
# would feed a false "problem" into the AI revision pass, which would then
# shrink real, correctly-generated prose paragraphs back into fragments.

def _paragraph_length_bullet():
    return bullet("This is a deliberately long bullet point that exceeds the two hundred "
                   "character poor-hierarchy threshold by being written as a full paragraph "
                   "of connected prose rather than a short, single-idea slide bullet fragment.")


def test_paragraph_length_bullet_flagged_for_pptx():
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[_paragraph_length_bullet()]),
        Slide(order=2, title="Thank You", content_blocks=[bullet("Questions?")]),
    ])
    _, report = validate_and_fix(outline, export_format="pptx")
    assert any("paragraph-length bullet" in i for i in report.issues)


def test_paragraph_length_bullet_not_flagged_for_document_docx():
    """The exact same outline that trips the check for pptx must NOT
    trip it for document_docx — same content, different format,
    different verdict, by design."""
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[_paragraph_length_bullet()]),
        Slide(order=2, title="Thank You", content_blocks=[bullet("Questions?")]),
    ])
    _, report = validate_and_fix(outline, export_format="document_docx")
    assert not any("paragraph-length bullet" in i for i in report.issues)


def test_format_defaults_to_pptx_behavior_when_unset():
    """validate_and_fix(outline) with no export_format argument at all
    (every pre-ADR-054 call site) must keep flagging this exactly as
    it always did — additive, not a silent behavior change for
    unmigrated callers."""
    outline = make_outline([
        Slide(order=1, title="Intro", content_blocks=[_paragraph_length_bullet()]),
        Slide(order=2, title="Thank You", content_blocks=[bullet("Questions?")]),
    ])
    _, report = validate_and_fix(outline)  # no export_format passed
    assert any("paragraph-length bullet" in i for i in report.issues)


def _overflow_risk_slide():
    # OVERFLOW_BUDGET_BY_LAYOUT defaults to 420 chars for "bullet_list"
    # — comfortably exceeded by several long bullets combined. Must be
    # DISTINCT text per bullet — identical repeated bullets get removed
    # by the earlier dedupe-repeated-bullets check before this one ever
    # runs, which would silently drop the total back under budget.
    return Slide(order=1, title="Crowded", content_blocks=[
        bullet("a" * 150), bullet("b" * 150), bullet("c" * 150),
    ])


def test_overflow_risk_flagged_for_pptx():
    outline = make_outline([_overflow_risk_slide(), Slide(order=2, title="Thank You", content_blocks=[bullet("Questions?")])])
    _, report = validate_and_fix(outline, export_format="pptx")
    assert any("crowded" in i for i in report.issues)


def test_overflow_risk_not_flagged_for_document_docx():
    outline = make_outline([_overflow_risk_slide(), Slide(order=2, title="Thank You", content_blocks=[bullet("Questions?")])])
    _, report = validate_and_fix(outline, export_format="document_docx")
    assert not any("crowded" in i for i in report.issues)

