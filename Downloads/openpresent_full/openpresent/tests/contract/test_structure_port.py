import pytest
from backend.adapters.structure.rule_based import RuleBasedStructureAdapter

ADAPTERS = [RuleBasedStructureAdapter()]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_rejects_empty_text(adapter):
    with pytest.raises(ValueError):
        adapter.build_outline("   ", "student_school")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_produces_at_least_one_slide(adapter):
    outline = adapter.build_outline("Photosynthesis is how plants make energy from light.", "student_school")
    assert len(outline.slides) >= 1


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_handles_headed_document(adapter):
    text = (
        "Introduction\n"
        "This paper discusses climate change and its effects on coastal cities.\n\n"
        "Methods\n"
        "We reviewed twenty peer-reviewed studies published between 2015 and 2024.\n\n"
        "Conclusion\n"
        "Coastal cities must adapt infrastructure to rising sea levels.\n"
    )
    outline = adapter.build_outline(text, "student_university")
    titles = [s.title for s in outline.slides]
    assert "Introduction" in titles
    assert "Methods" in titles
    assert "Conclusion" in titles


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_thin_unpunctuated_content_produces_no_duplicate_slides(adapter):
    """Regression test for a real bug found during the quiet launch:
    short, unpunctuated input (e.g. 'my name is X, I am 21, I live in Y')
    was producing 3 slides — a garbled mid-word-truncated title, a
    'Key Point 1' slide that duplicated nearly the entire same text,
    and a padded 'Questions?' closer. Fixed to produce a minimal,
    honest 2-slide result instead."""
    text = "my name is ague jean baptiste ismaila i am 21 years old and i live currently in Russia i am from senegal"
    outline = adapter.build_outline(text, "student_school")
    assert len(outline.slides) == 2  # title + one overview slide, no padding
    assert outline.slides[1].title == "Overview"
    # The full text must appear intact somewhere (on the content slide),
    # not truncated/lost.
    body_text = outline.slides[1].content_blocks[0].text
    assert body_text == text


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_titles_never_cut_off_mid_word(adapter):
    """Regression test: titles must truncate at word boundaries, never
    mid-word (the original bug produced titles like '...21 years old a…')."""
    long_run_on = "a" * 30 + " " + "b" * 30 + " " + "c" * 30  # no punctuation at all
    outline = adapter.build_outline(long_run_on, "student_school")
    title = outline.slides[0].title
    # A mid-word cut would leave a fragment shorter than a full "word"
    # (e.g. "aaaaa…" cut from "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa") — check
    # the title, minus the ellipsis, ends on a real word boundary from
    # the source text (i.e. is a prefix ending exactly at a space in
    # the original, not an arbitrary character offset).
    clean_title = title.rstrip("…").rstrip(",;: ")
    assert long_run_on.startswith(clean_title)
    assert not long_run_on[len(clean_title):len(clean_title) + 1].isalnum() or \
        clean_title == long_run_on  # next char after cut is a boundary, not mid-word


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_handles_unstructured_notes(adapter):
    text = (
        "just some rough notes about the water cycle and evaporation and clouds "
        "forming rain, covering enough ground that it should not be treated as "
        "thin content for the purposes of this particular test case"
    )
    outline = adapter.build_outline(text, "student_school")
    assert len(outline.slides) >= 1


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_markdown_bold_headers_recognized_as_headings(adapter):
    """Regression test for a real bug: markdown-formatted section
    headers ('**EDUCATION**') were not recognized as headings at all,
    causing every content slide to fall back to a generic repeated
    'Overview' label with no way to distinguish slides."""
    text = (
        "**JORDAN ALEXANDER**\n"
        "Dynamic and results-driven Marketing Manager with over 8 years of experience.\n\n"
        "**EDUCATION**\n"
        "Master of Business Administration (MBA), Boston University.\n\n"
        "**SKILLS**\n"
        "Leadership, strategy, and communication.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    titles = [s.title for s in outline.slides]
    assert "EDUCATION" in titles
    assert "SKILLS" in titles
    # No leftover markdown asterisks anywhere in the output.
    assert not any("*" in t for t in titles)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_prose_sentence_is_not_mistaken_for_a_heading(adapter):
    """Regression test: a full sentence that merely starts with a
    capital letter ('Dynamic and results-driven Marketing Manager
    with over 8 years of experience...') must NOT be treated as a
    section heading — only short, genuinely title-like phrases should be."""
    text = (
        "**PROFILE**\n"
        "Dynamic and results-driven Marketing Manager with over 8 years of experience "
        "in digital strategy, brand management, and team leadership.\n\n"
        "**EDUCATION**\n"
        "Master of Business Administration.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    titles = [s.title for s in outline.slides]
    assert not any("Dynamic and results-driven" in t for t in titles)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_instructional_footer_is_excluded(adapter):
    """Regression test: AI-tool-generated 'how to use this' instructional
    text must be filtered out entirely, not treated as slide content."""
    text = (
        "**SUMMARY**\n"
        "Experienced professional with a strong background in project management.\n\n"
        "How to use this for a PowerPoint Presentation:\n"
        "When you paste this into Notepad, use the bolded headers as slide titles.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    all_text = " ".join(
        s.title + " " + " ".join(b.text for b in s.content_blocks)
        for s in outline.slides
    ).lower()
    assert "how to use this" not in all_text
    assert "paste this into" not in all_text


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_bullet_list_items_are_not_joined_without_spaces(adapter):
    """Regression test: wrapped lines and markdown bullet items were
    being joined with no space at all, producing artifacts like
    'recordof' instead of 'record of'. Bullet markers must each become
    a separate, cleanly-joined item."""
    text = (
        "**EXPERIENCE**\n"
        "- Managed a team of 12 marketing professionals, fostering a collaborative\n"
        "environment that increased department productivity by 25 percent.\n"
        "- Oversaw a large annual marketing budget, strategically allocating resources\n"
        "to high performing channels.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    experience_slide = next(
        s for s in outline.slides if s.title == "EXPERIENCE" and s.content_blocks
    )
    all_bullet_text = " ".join(b.text for b in experience_slide.content_blocks)
    assert "recordof" not in all_bullet_text.replace(" ", "")  # sanity: no accidental smoke test artifact
    assert "environmentthat" not in all_bullet_text
    assert "resourcesto" not in all_bullet_text
    assert len(experience_slide.content_blocks) == 2  # two distinct bullet items, not merged into one


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resume_like_content_gets_thank_you_closer(adapter):
    """Regression test: resume-like documents should close with
    'Thank You' rather than the generic 'Questions?'."""
    text = (
        "**SUMMARY**\nExperienced marketing professional.\n\n"
        "**EXPERIENCE**\nManaged multiple campaigns successfully.\n\n"
        "**EDUCATION**\nMBA from a top university.\n\n"
        "**SKILLS**\nLeadership and strategy.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    assert outline.slides[-1].title == "Thank You"



