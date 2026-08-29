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
def test_resume_like_content_gets_contact_info_closer(adapter):
    """Regression test: resume-like documents should close with
    'Contact Information' (per the Resume recipe, Phase 3.5 Step 2) —
    more useful for a resume audience than the generic 'Questions?'
    or the older, less specific 'Thank You'."""
    text = (
        "**SUMMARY**\nExperienced marketing professional.\n\n"
        "**EXPERIENCE**\nManaged multiple campaigns successfully.\n\n"
        "**EDUCATION**\nMBA from a top university.\n\n"
        "**SKILLS**\nLeadership and strategy.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    assert outline.slides[-1].title == "Contact Information"
    assert outline.document_type == "resume"


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_no_empty_overview_slide_when_title_has_no_intro(adapter):
    """Regression test: a document whose title is immediately followed
    by a real section (no free-standing intro paragraph under the
    title) must not produce an empty 'Overview' placeholder slide."""
    text = (
        "**The Poetry of Particles**\n\n"
        "**Abstract**\nThis paper explores quantum mechanics in depth.\n\n"
        "**Introduction**\nPhysics studies the fundamental forces of the universe.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    titles = [s.title for s in outline.slides]
    assert "Overview" not in titles
    assert "(No additional detail provided)" not in " ".join(
        b.text for s in outline.slides for b in s.content_blocks
    )


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_closing_slide_not_duplicated_when_section_already_matches(adapter):
    """Regression test: if the recipe's closing slide title (e.g.
    'Discussion' for academic papers) already appears as a real section
    heading anywhere in the document, don't add a second, duplicate
    slide with the same title."""
    text = (
        "**A Study**\n\n"
        "**Abstract**\nSummary of the study.\n\n"
        "**Methodology**\nHow the study was conducted.\n\n"
        "**Discussion**\nWhat the results mean.\n\n"
        "**Conclusion**\nFinal thoughts.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    titles = [s.title for s in outline.slides]
    assert titles.count("Discussion") == 1
    assert outline.document_type == "academic"


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resume_sections_reordered_to_canonical_order(adapter):
    """Regression test: a resume listing sections out of conventional
    order (e.g. Education before Experience) should be reordered to
    the canonical presentation order (Experience before Education),
    per the Resume recipe."""
    text = (
        "**JORDAN ALEXANDER**\n\n"
        "**Education**\nMBA from a top university.\n\n"
        "**Experience**\nManaged multiple campaigns for eight years.\n"
    )
    outline = adapter.build_outline(text, "student_school")
    titles = [s.title for s in outline.slides]
    assert titles.index("Experience") < titles.index("Education")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_academic_and_business_and_lecture_recipes_apply_correct_closer(adapter):
    """Regression test: each document type's closing slide matches its
    recipe, confirming the classifier -> recipe wiring works end to end
    for types beyond resume."""
    academic = adapter.build_outline(
        "**Abstract**\nA study.\n\n**Methodology**\nHow it was done.\n", "student_school"
    )
    assert academic.slides[-1].title == "Discussion"

    business = adapter.build_outline(
        "**Executive Summary**\nOverview.\n\n**KPIs**\nKey metrics.\n", "student_school"
    )
    assert business.slides[-1].title == "Recommendations"

    lecture = adapter.build_outline(
        "**Lecture Overview**\nToday's topic.\n\n**Key Concept**\nThe main idea.\n", "student_school"
    )
    assert lecture.slides[-1].title == "Summary"


# -- Format-aware content shape (ADR-054) -----------------------------------
# Before this, plain prose with no bullet markers was ALWAYS split on
# sentence boundaries into one-bullet-per-sentence fragments — correct for
# a slide deck, but it shattered a source document's own real paragraphs
# into a list that was never meant to be one, which is why a generated
# Word document read like a reformatted deck even when the uploaded
# source was written in normal connected prose.

PROSE_SECTION = (
    "Introduction\n"
    "Solar power costs have dropped by roughly eighty percent over the past decade. "
    "This dramatic decline has been driven by manufacturing scale and improved panel "
    "efficiency. Residential adoption has nearly doubled year over year in several "
    "major markets as a result.\n"
)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_plain_prose_stays_one_paragraph_for_document_docx(adapter):
    outline = adapter.build_outline(PROSE_SECTION, "general", export_format="document_docx")
    # With only one detected section matching the doc title, the title
    # slide and content slide legitimately share the same "Introduction"
    # title, and a closing slide ("Questions?") gets auto-added too —
    # filter specifically to slides carrying real BULLET content (not
    # just any content_blocks, which the closing slide's NOTE satisfies
    # too), rather than assuming a fixed total slide count.
    bullet_slides = [
        s for s in outline.slides
        if any(b.type.value == "bullet" for b in s.content_blocks)
    ]
    assert len(bullet_slides) == 1  # not split across multiple slides/sections
    bullets = [b.text for b in bullet_slides[0].content_blocks if b.type.value == "bullet"]
    assert len(bullets) == 1  # the whole section is ONE connected paragraph, not one bullet per sentence
    assert bullets[0].endswith(".")
    assert "eighty percent" in bullets[0] and "Residential adoption" in bullets[0]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_plain_prose_still_splits_per_sentence_for_pptx(adapter):
    """The exact same source text must produce the ORIGINAL
    sentence-per-bullet behavior for pptx — same content, different
    target format, different shape, by design. Confirms this is a
    genuine format branch, not an accidental global behavior change."""
    outline = adapter.build_outline(PROSE_SECTION, "general", export_format="pptx")
    intro_slides = [s for s in outline.slides if s.title == "Introduction"]
    all_bullets = [
        b.text for s in intro_slides for b in s.content_blocks if b.type.value == "bullet"
    ]
    assert len(all_bullets) == 3  # three sentences -> three separate bullets, unchanged behavior


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_format_defaults_to_pptx_behavior_when_unset(adapter):
    """build_outline(text, audience) with no export_format argument at
    all (every pre-ADR-054 call site) must keep splitting sentences
    exactly as it always did."""
    outline = adapter.build_outline(PROSE_SECTION, "general")  # export_format not passed
    intro_slides = [s for s in outline.slides if s.title == "Introduction"]
    all_bullets = [
        b.text for s in intro_slides for b in s.content_blocks if b.type.value == "bullet"
    ]
    assert len(all_bullets) == 3


GENUINE_LIST_SECTION = (
    "Key Deliverables\n"
    "- Ship the new onboarding flow\n"
    "- Launch mobile app beta\n"
    "- Complete SOC 2 audit\n"
)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_genuine_bullet_list_still_splits_per_item_for_document_docx(adapter):
    """A real list in the SOURCE document (explicit bullet markers)
    must stay a real list even when the target is document_docx — the
    prose-preservation fix only applies to sentence-splitting of plain
    prose, never to content that was genuinely authored as a list."""
    outline = adapter.build_outline(GENUINE_LIST_SECTION, "general", export_format="document_docx")
    deliverable_slides = [s for s in outline.slides if s.title == "Key Deliverables"]
    all_bullets = [
        b.text for s in deliverable_slides for b in s.content_blocks if b.type.value == "bullet"
    ]
    assert len(all_bullets) == 3
    assert "Ship the new onboarding flow" in all_bullets

