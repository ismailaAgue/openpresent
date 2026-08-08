"""
Generation engine — Technical Blueprint Section 5, "Request Flow."

Orchestrates: Ingestion -> Structure (rule-based, classified + recipe-
driven per ADR-020) -> AI Port (optional enhancement) -> Design -> Export.

This is Path A + the optional Path B enhancement step in one function.
Path A alone (AI unavailable) must always produce a usable result —
that's the guarantee this engine exists to enforce structurally.

Phase 3.5 Step 3 (ADR-021): wires the AI Port's `rewrite` capability
— already built in Phase 2, never actually called anywhere until now
— into the title slide specifically. Reviewer feedback's own example
("The Role of Government in Market Economies" -> "Why Markets Need
Rules") is exactly this: making a plain, document-derived title more
presentation-friendly. Deliberately scoped to ONLY the title slide —
section headings and recipe-driven closing slides (e.g. "Discussion,"
"Contact Information") are real document structure or deliberate
recipe design, not raw text needing improvement, and rewriting them
would undermine the classifier/recipe system from ADR-020.
"""

import uuid
from backend.adapters import registry
from backend.models.recipe import Recipe

MAX_REWRITTEN_TITLE_LENGTH = 80
TITLE_REWRITE_INSTRUCTIONS = (
    "Rewrite this as a short, punchy, presentation-friendly slide title. "
    "Maximum 6 words. Return ONLY the new title, nothing else — no quotes, "
    "no explanation."
)


def generate_presentation(file_bytes: bytes, filename: str, export_format: str = "pptx",
                           audience_type: str = "student_school", language: str = "en",
                           project_id: str | None = None) -> tuple[Recipe, bytes]:
    project_id = project_id or str(uuid.uuid4())

    ingestion = registry.get_ingestion_adapter(filename)
    source_text = ingestion.extract_text(file_bytes, filename)

    structure = registry.get_structure_adapter()
    outline = structure.build_outline(source_text, audience_type)

    ai = registry.get_ai_adapter()
    if ai.is_available():
        outline = ai.propose_structure(outline, source_text)
        _apply_title_enhancement(outline, ai)
    # If AI is unavailable, outline stays exactly as the rule-based
    # engine produced it — no error, no block, no visible difference
    # to the calling code. This is the enforced guarantee, not a hope.

    design = registry.get_design_adapter()
    from backend.models.recipe import Theme
    recipe = design.apply_theme(
        project_id=project_id,
        source_text=source_text,
        outline=outline,
        theme=Theme(),
        audience_type=audience_type,
        language=language,
    )

    exporter = registry.get_export_adapter(export_format)
    file_out = exporter.export(recipe)

    return recipe, file_out


def _apply_title_enhancement(outline, ai) -> None:
    """Improve only the title slide's title via AI rewrite, in place.
    Never raises, never leaves the outline in a worse state than
    before — an empty, absurdly long, or otherwise unusable AI result
    is silently discarded in favor of the original rule-based title."""
    if not outline.slides:
        return
    title_slide = outline.slides[0]
    original = title_slide.title
    try:
        rewritten = ai.rewrite(original, instructions=TITLE_REWRITE_INSTRUCTIONS)
    except Exception:
        return  # AI Port methods shouldn't raise, but never trust that blindly here

    rewritten = (rewritten or "").strip().strip('"').strip("'")
    if not rewritten or len(rewritten) > MAX_REWRITTEN_TITLE_LENGTH:
        return  # keep the original rule-based title
    title_slide.title = rewritten
