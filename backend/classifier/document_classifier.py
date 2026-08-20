"""
Document Classifier — Phase 3.5 Step 2.

Pure rule-based keyword scoring, no AI (Constitution Principle 1).
Headings are much stronger signals than body-text occurrences: a
section literally titled "Experience" is far more reliable evidence
than the word "experience" appearing once in a sentence, so heading
matches are weighted heavily above body matches.

This is deliberately simple and inspectable — every classification
can be explained by which keywords matched where, which matters for
debugging misclassifications later.
"""

import re
from backend.models.document_type import DocumentType

HEADING_MATCH_WEIGHT = 3
BODY_MATCH_WEIGHT = 1

_KEYWORDS: dict[DocumentType, set[str]] = {
    DocumentType.RESUME: {
        "experience", "education", "skills", "employment", "career",
        "summary", "references", "certifications", "linkedin",
        "objective", "work history", "achievements", "competencies",
        "professional summary", "core competencies",
    },
    DocumentType.ACADEMIC: {
        "abstract", "methodology", "literature review", "hypothesis",
        "citation", "findings", "research question", "peer review",
        "bibliography",
    },
    DocumentType.BUSINESS: {
        "kpi", "kpis", "revenue", "quarter", "stakeholders", "roi",
        "budget", "market share", "strategy", "recommendations",
        "executive summary", "forecast", "deliverables", "quarterly",
        "profit", "growth targets",
    },
    DocumentType.LECTURE: {
        "lecture", "chapter", "concept", "example", "exercise",
        "homework", "syllabus", "definition", "theorem",
        "class notes", "topic", "learning objective", "assignment",
    },
}

# Keyword sets favor distinctive, genre-specific terms over generic
# ones ("introduction," "conclusion," "results," "discussion" were
# deliberately left out even though academic papers use them, because
# they're common enough across other document types — a personal essay
# with a "Conclusion" heading isn't an academic paper — that including
# them caused false positives. Distinctive terms are more reliable
# signals even though they appear less often.


class DocumentClassifier:
    def classify(self, source_text: str, headings: list[str] | None = None) -> DocumentType:
        headings = headings or []
        heading_text_lower = " ".join(h.lower() for h in headings)
        body_lower = source_text.lower()

        scores: dict[DocumentType, int] = {dtype: 0 for dtype in _KEYWORDS}
        for dtype, keywords in _KEYWORDS.items():
            for kw in keywords:
                if _contains_word(heading_text_lower, kw):
                    scores[dtype] += HEADING_MATCH_WEIGHT
                elif _contains_word(body_lower, kw):
                    scores[dtype] += BODY_MATCH_WEIGHT

        best_type, best_score = max(scores.items(), key=lambda kv: kv[1])
        if best_score == 0:
            return DocumentType.GENERAL
        return best_type


def _contains_word(text: str, phrase: str) -> bool:
    """Word-boundary-safe substring check — avoids 'career' matching
    inside an unrelated longer word, and works for multi-word phrases."""
    pattern = r"\b" + re.escape(phrase) + r"\b"
    return re.search(pattern, text) is not None
