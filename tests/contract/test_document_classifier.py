import pytest
from backend.classifier.document_classifier import DocumentClassifier
from backend.models.document_type import DocumentType

classifier = DocumentClassifier()


def test_classifies_resume():
    text = "JORDAN ALEXANDER"
    headings = ["Summary", "Experience", "Education", "Skills"]
    assert classifier.classify(text, headings) == DocumentType.RESUME


def test_classifies_academic_paper():
    text = "A study of quantum effects."
    headings = ["Abstract", "Introduction", "Methodology", "Results", "Discussion", "References"]
    assert classifier.classify(text, headings) == DocumentType.ACADEMIC


def test_classifies_business_report():
    text = "Quarterly performance overview."
    headings = ["Executive Summary", "Revenue", "KPIs", "Market Share", "Recommendations"]
    assert classifier.classify(text, headings) == DocumentType.BUSINESS


def test_classifies_lecture_notes():
    text = "Notes for this week's class."
    headings = ["Lecture Overview", "Key Concept", "Example", "Exercise", "Summary"]
    assert classifier.classify(text, headings) == DocumentType.LECTURE


def test_classifies_general_when_no_strong_signal():
    text = "A short story about a trip to the mountains last summer."
    headings = ["The Trip", "What We Saw", "Conclusion"]
    assert classifier.classify(text, headings) == DocumentType.GENERAL


def test_heading_match_outweighs_incidental_body_mention():
    """A resume-like heading set should win even if the body text
    happens to mention an academic-sounding word once in passing."""
    text = "This methodology of managing a team worked well for years."
    headings = ["Experience", "Education", "Skills"]
    assert classifier.classify(text, headings) == DocumentType.RESUME


def test_classify_without_headings_falls_back_to_body_text():
    """The classifier must still work when no headings were detected
    at all (e.g. thin/unstructured input) — using body text alone."""
    text = "I have extensive experience and education in this field, with strong skills."
    result = classifier.classify(text, headings=[])
    assert result == DocumentType.RESUME


def test_generic_project_document_not_misclassified_as_lecture():
    """Regression test: a project/business document that references
    'week' repeatedly (e.g. 'week one', 'week four' in a timeline) must
    not be misclassified as lecture content — 'week' alone is too
    generic a signal, found via real testing of the Process layout."""
    text = (
        "Kickoff meeting scheduled for week one. "
        "Design phase runs through week four. "
        "Development continues into week eight."
    )
    result = classifier.classify(text, headings=["Project Timeline"])
    assert result != DocumentType.LECTURE
