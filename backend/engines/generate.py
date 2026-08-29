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
from typing import Callable
from backend.adapters import registry
from backend.models.recipe import Recipe
from backend.monitoring.sentry_setup import capture_exception
from backend.ports.brand import BrandProfile

MAX_REWRITTEN_TITLE_LENGTH = 80
TITLE_REWRITE_INSTRUCTIONS = (
    "Rewrite this as a short, punchy, presentation-friendly slide title. "
    "Maximum 6 words. Return ONLY the new title, nothing else — no quotes, "
    "no explanation."
)

# ADR-040 — same stage vocabulary as engines/ai_generate.py's topic
# pipeline, so the frontend's step indicator works identically for both
# job types. This pipeline is single-pass rule-based structure + optional
# AI enhancement (not the topic pipeline's separate outline/content/layout
# calls), so only 4 of the 6 shared labels apply here — deliberately not
# padded out with stages that don't correspond to real work in this path.
STAGE_UNDERSTANDING = "understanding_request"
STAGE_OUTLINE = "building_outline"
STAGE_CONTENT = "generating_content"
STAGE_DESIGN = "applying_design"


def _report(on_stage: Callable[[str], None] | None, stage: str) -> None:
    if on_stage is None:
        return
    try:
        on_stage(stage)
    except Exception as e:
        capture_exception(e, tags={"stage": "progress_report"})


def generate_presentation(file_bytes: bytes, filename: str, export_format: str = "pptx",
                           audience_type: str = "student_school", language: str = "en",
                           target_slide_count: int | None = None,
                           project_id: str | None = None,
                           on_stage: Callable[[str], None] | None = None,
                           brand: BrandProfile | None = None) -> tuple[Recipe, bytes]:
    project_id = project_id or str(uuid.uuid4())

    _report(on_stage, STAGE_UNDERSTANDING)
    ingestion = registry.get_ingestion_adapter(filename)
    source_text = ingestion.extract_text(file_bytes, filename)

    _report(on_stage, STAGE_OUTLINE)
    structure = registry.get_structure_adapter()
    outline = structure.build_outline(source_text, audience_type, export_format=export_format)

    ai = registry.get_ai_adapter()
    if ai.is_available():
        _report(on_stage, STAGE_CONTENT)
        try:
            outline = ai.propose_structure(outline, source_text, target_slide_count=target_slide_count)
            _apply_title_enhancement(outline, ai, brand)
        except Exception as e:
            # AIPort methods are contractually never supposed to raise
            # (they should self-degrade), but this is the last line of
            # defense — spec Section 16: "AI provider failures" are a
            # named monitoring target regardless of where they surface.
            capture_exception(e, tags={"stage": "ai_enhancement", "filename": filename})

        # ADR-034: language was previously stored on the Recipe as
        # metadata only — it never actually translated anything, which
        # made exposing it as a user-facing choice hollow. Now: when a
        # non-English language is requested and AI is available, every
        # slide's title, bullets, and notes are translated in place. AI
        # unavailable or a translation call failing degrades to the
        # untranslated (English) text — never blocks generation.
        if language != "en":
            _apply_translation(outline, ai, language)
    # If AI is unavailable, outline stays exactly as the rule-based
    # engine produced it — no error, no block, no visible difference
    # to the calling code. This is the enforced guarantee, not a hope.

    _report(on_stage, STAGE_DESIGN)
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

    try:
        exporter = registry.get_export_adapter(export_format)
        file_out = exporter.export(recipe)
    except Exception as e:
        capture_exception(e, tags={"stage": "export", "export_format": export_format})
        raise

    return recipe, file_out


def _apply_translation(outline, ai, language: str) -> None:
    """Translates every slide's title, bullets, and notes in place —
    ADR-034. Each individual translate() call already self-degrades
    (returns the original text) on failure per the AIPort contract, so
    no try/except is needed here beyond what propose_structure/rewrite
    already demonstrate — a failed translation of one bullet just
    leaves that one bullet in English, never blocks the rest."""
    from backend.models.recipe import BlockType
    for slide in outline.slides:
        slide.title = ai.translate(slide.title, language) or slide.title
        for block in slide.content_blocks:
            if block.type in (BlockType.BULLET, BlockType.NOTE) and block.text:
                block.text = ai.translate(block.text, language) or block.text


def _apply_title_enhancement(outline, ai, brand: BrandProfile | None = None) -> None:
    """Improve only the title slide's title via AI rewrite, in place.
    Never raises, never leaves the outline in a worse state than
    before — an empty, absurdly long, or otherwise unusable AI result
    is silently discarded in favor of the original rule-based title.

    ADR-045 (Brand Memory, closing the document-mode gap left open
    when Brand Memory first shipped): if the workspace has a brand
    profile, its tone/visual_style — the two fields actually about
    phrasing rather than content — are appended to the rewrite
    instructions. This is the ONE AI touchpoint in this pipeline about
    phrasing/tone (propose_structure is about document structure, not
    style, so it's not a natural fit for brand tone the way this is —
    same reasoning the topic pipeline's Strategy stage used to decide
    where brand context belongs)."""
    if not outline.slides:
        return
    title_slide = outline.slides[0]
    original = title_slide.title
    instructions = TITLE_REWRITE_INSTRUCTIONS
    if brand and not brand.is_empty() and (brand.tone or brand.visual_style):
        brand_hint = " ".join(filter(None, [
            f"Match this brand's tone: {brand.tone}." if brand.tone else "",
            f"Visual style direction: {brand.visual_style}." if brand.visual_style else "",
        ]))
        instructions = f"{TITLE_REWRITE_INSTRUCTIONS} {brand_hint}"
    try:
        rewritten = ai.rewrite(original, instructions=instructions)
    except Exception:
        return  # AI Port methods shouldn't raise, but never trust that blindly here

    rewritten = (rewritten or "").strip().strip('"').strip("'")
    if not rewritten or len(rewritten) > MAX_REWRITTEN_TITLE_LENGTH:
        return  # keep the original rule-based title
    title_slide.title = rewritten
