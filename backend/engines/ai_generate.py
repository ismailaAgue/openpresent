"""
Topic-first generation engine — ADR-028 (AI-first pivot).

This is the new sibling to backend/engines/generate.py (document
upload -> deck). That engine is untouched; this one implements the
other entry point the spec's Success Criteria (Section 19) describes:
topic + slide count + audience + language -> deck, no source document.

Pipeline (spec Section 3), mapped to what actually runs:

  User Request
    -> Planner / Strategy / Outline / Slide Content   [AIPipelinePort.generate_presentation_outline
                                                         — one combined call, see ports/ai_pipeline.py]
    -> Layout Planning / Image Planning                [DesignPort.apply_theme — deterministic, unchanged]
    -> Quality Review                                  [validate_and_fix — deterministic, $0]
    -> Revision Pass (if necessary)                    [AIPipelinePort.review_and_revise — optional,
                                                         config-gated]
    -> Presentation JSON (Recipe)
    -> Renderer (ExportPort)
    -> Export

Every stage after the first degrades gracefully to something
deterministic, per Constitution Principle 3 — a Gemini outage never
takes generation down, it just quietly drops to the deterministic
topic template.
"""

import os
import uuid
from backend.adapters import registry
from backend.models.recipe import Recipe, Theme
from backend.ports.ai_pipeline import GenerationRequest, QualityReport
from backend.ports.export import UnsupportedFormatError
from backend.pipeline.deterministic_topic_outline import build_deterministic_outline
from backend.validation.quality_validator import validate_and_fix


def generate_presentation_from_topic(
    topic: str,
    slide_count: int = 10,
    audience_type: str = "general",
    language: str = "en",
    tone: str = "professional",
    export_format: str = "pptx",
    project_id: str | None = None,
) -> tuple[Recipe, bytes, QualityReport]:
    if not topic or not topic.strip():
        raise ValueError("topic must not be empty")

    project_id = project_id or str(uuid.uuid4())
    request = GenerationRequest(
        topic=topic.strip(), slide_count=slide_count,
        audience_type=audience_type, language=language, tone=tone,
    )

    outline = None
    pipeline = registry.get_ai_pipeline_adapter()
    if pipeline.is_available():
        try:
            outline = pipeline.generate_presentation_outline(request)
        except Exception:
            outline = None  # any failure (network, malformed JSON, wrong slide count) -> fall back

    if outline is None or not outline.slides:
        outline = build_deterministic_outline(request)

    outline, quality_report = validate_and_fix(outline)

    # Optional, bounded, config-gated: a second AI call to fix issues
    # the deterministic validator flagged but couldn't fix itself
    # (Cost Policy — this is the one stage explicitly opt-in, since
    # it's the one that costs another full model call).
    revision_enabled = os.environ.get("OPENPRESENT_AI_QUALITY_REVIEW", "false").lower() == "true"
    if revision_enabled and pipeline.is_available() and quality_report.issues:
        try:
            revised = pipeline.review_and_revise(outline, quality_report, request)
            outline, quality_report = validate_and_fix(revised)
        except Exception:
            pass  # keep the pre-revision outline; it already passed validation

    # Layout + image-query assignment: deterministic, unchanged design
    # engine (spec Section 11 — "AI should never directly control
    # formatting"). source_text is the topic itself for provenance/
    # regeneration context, matching how the document flow stores the
    # original text.
    design = registry.get_design_adapter()
    recipe = design.apply_theme(
        project_id=project_id,
        source_text=f"Topic: {topic.strip()}",
        outline=outline,
        theme=Theme(),
        audience_type=audience_type,
        language=language,
    )

    try:
        exporter = registry.get_export_adapter(export_format)
    except UnsupportedFormatError:
        raise
    output_bytes = exporter.export(recipe)

    return recipe, output_bytes, quality_report
