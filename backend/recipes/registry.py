"""
Concrete Recipes per document type — Phase 3.5 Step 2.

Values here are the actual product decisions from the reviewer
feedback: resumes get tight, punchy density and end with contact info,
not "Questions?"; academic papers get a bit more room per slide (ideas
are denser) and end with "Discussion"; business docs end with
"Recommendations"; lecture material ends with "Summary".
"""

from backend.models.document_type import DocumentType
from backend.recipes.base import Recipe

RESUME_RECIPE = Recipe(
    max_bullets_per_slide=4,
    closing_slide_title="Contact Information",
    canonical_section_order=(
        "summary", "profile", "objective",
        "experience", "work history", "employment",
        "skills", "competencies",
        "education",
        "certifications", "references",
    ),
)

ACADEMIC_RECIPE = Recipe(
    max_bullets_per_slide=5,
    closing_slide_title="Discussion",
    canonical_section_order=(
        "abstract", "introduction",
        "methodology", "literature review",
        "results", "findings",
        "discussion", "conclusion",
        "references",
    ),
)

BUSINESS_RECIPE = Recipe(
    max_bullets_per_slide=4,
    closing_slide_title="Recommendations",
    canonical_section_order=(
        "executive summary", "overview",
        "market", "strategy",
        "results", "kpis", "revenue",
        "recommendations", "forecast",
    ),
)

LECTURE_RECIPE = Recipe(
    max_bullets_per_slide=5,
    closing_slide_title="Summary",
    canonical_section_order=(
        "introduction", "overview",
        "concept", "definition",
        "example", "exercise",
        "summary",
    ),
)

GENERAL_RECIPE = Recipe(
    max_bullets_per_slide=5,
    closing_slide_title="Questions?",
    canonical_section_order=(),
)

_RECIPES: dict[DocumentType, Recipe] = {
    DocumentType.RESUME: RESUME_RECIPE,
    DocumentType.ACADEMIC: ACADEMIC_RECIPE,
    DocumentType.BUSINESS: BUSINESS_RECIPE,
    DocumentType.LECTURE: LECTURE_RECIPE,
    DocumentType.GENERAL: GENERAL_RECIPE,
}


def get_recipe(document_type: DocumentType) -> Recipe:
    return _RECIPES[document_type]
