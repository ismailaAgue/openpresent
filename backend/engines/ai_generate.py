"""
Topic-first generation engine — ADR-028 (AI-first pivot), substantially
rewritten ADR-030 (proper multi-stage pipeline).

Pipeline (spec Section 3), mapped to what actually runs now:

  User Request
    -> Research / Knowledge Expansion (optional)  [ResearchPort.research — off by default]
    -> Planner / Strategy                          [AIPipelinePort.generate_strategy]
    -> Outline Generation                          [AIPipelinePort.generate_outline_structure]
    -> Slide Content Generation                    [AIPipelinePort.generate_slide_content]
    -> Layout Planning / Image Planning            [AIPipelinePort.plan_layout — AI-driven, ADR-030;
                                                     DesignPort's rule-based classifier is the
                                                     deterministic FALLBACK, not removed]
    -> Quality Review                              [validate_and_fix — deterministic, $0, always runs]
    -> Revision Pass (if necessary)                [AIPipelinePort.review_and_revise — now runs by
                                                     default whenever real issues remain, not opt-in]
    -> Presentation JSON (Recipe)                  [DesignPort.apply_theme]
    -> Renderer (ExportPort)
    -> Export

Every AI stage degrades gracefully, per Constitution Principle 3 — any
failure anywhere in the multi-call chain (network error, malformed
JSON, provider outage on every configured provider) drops the WHOLE
AI attempt back to the deterministic topic template, never a
half-AI/half-broken deck. This is a deliberate all-or-nothing boundary
around the AI portion of the pipeline: partially trusting an outline
that failed partway through validation would be worse than a clean,
fully-deterministic fallback.
"""

import os
import random
import uuid
from backend.adapters import registry
from backend.models.recipe import Recipe, Theme
from backend.ports.ai_pipeline import GenerationRequest, QualityReport
from backend.ports.export import UnsupportedFormatError
from backend.pipeline.deterministic_topic_outline import build_deterministic_outline
from backend.pipeline.variety import pick_theme_variant
from backend.adapters.design.rule_based import get_theme_variant
from backend.validation.quality_validator import validate_and_fix
from backend.monitoring.sentry_setup import capture_exception, add_breadcrumb

MAX_REVISION_PASSES = 1  # bounded — spec Section 13: "allow AN automatic improvement pass"


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

    outline = _run_ai_pipeline(request)
    ai_layout_planned = outline is not None

    if outline is None:
        outline = build_deterministic_outline(request)

    outline, quality_report = validate_and_fix(outline)

    pipeline = registry.get_ai_pipeline_adapter()
    if pipeline.is_available() and quality_report.issues:
        for _ in range(MAX_REVISION_PASSES):
            if not quality_report.issues:
                break
            try:
                revised = pipeline.review_and_revise(outline, quality_report, request)
                outline, quality_report = validate_and_fix(revised)
                add_breadcrumb("quality_review", "revision pass applied",
                                data={"remaining_issues": len(quality_report.issues)})
            except Exception as e:
                capture_exception(e, tags={"stage": "quality_review"})
                break  # keep the pre-revision outline; it already passed validation

    # Layout + image-query assignment. AI-driven when the AI pipeline
    # itself produced this outline (ADR-030); otherwise (AI unavailable,
    # or every provider failed) the rule-based classifier in DesignPort
    # runs instead — the deterministic fallback, not removed.
    design = registry.get_design_adapter()
    # Presentation variety (spec Section 10): a random visual theme
    # variant for every topic-first generation — get_theme_variant()
    # returns a fully-resolved Theme (not just an overridden field),
    # which is what actually makes apply_theme() treat it as an
    # explicit choice rather than silently falling back to its own
    # document-type-based default (a real bug caught in testing: a
    # Theme() with only color_set_id set was being ignored entirely).
    theme = get_theme_variant(pick_theme_variant())
    recipe = design.apply_theme(
        project_id=project_id,
        source_text=f"Topic: {topic.strip()}",
        outline=outline,
        theme=theme,
        audience_type=audience_type,
        language=language,
        ai_layout_planned=ai_layout_planned,
    )

    try:
        exporter = registry.get_export_adapter(export_format)
    except UnsupportedFormatError:
        raise
    try:
        output_bytes = exporter.export(recipe)
    except Exception as e:
        capture_exception(e, tags={"stage": "export", "export_format": export_format})
        raise

    return recipe, output_bytes, quality_report


def _run_ai_pipeline(request: GenerationRequest):
    """Runs Research (optional) -> Strategy -> Outline Structure ->
    Slide Content -> Layout Planning as one all-or-nothing attempt.
    Returns a fully-formed Outline with layout_type/image_query already
    set, or None if AI is unavailable or any stage failed — callers
    treat None exactly like "fall back to the deterministic template"."""
    pipeline = registry.get_ai_pipeline_adapter()
    if not pipeline.is_available():
        return None

    research_brief = None
    research = registry.get_research_adapter()
    if research.is_available():
        try:
            research_brief = research.research(request.topic)
            add_breadcrumb("research", "completed", data={"fact_count": len(research_brief.facts)})
        except Exception as e:
            capture_exception(e, tags={"stage": "research"})
            research_brief = None  # research is optional — proceed without it, not fatal

    try:
        strategy = pipeline.generate_strategy(request, research_brief)
        add_breadcrumb("ai_pipeline", "strategy generated",
                        data={"narrative_style": strategy.narrative_style})

        structure = pipeline.generate_outline_structure(request, strategy)
        add_breadcrumb("ai_pipeline", "outline structure generated", data={"slides": len(structure)})

        outline = pipeline.generate_slide_content(request, strategy, structure)
        add_breadcrumb("ai_pipeline", "slide content generated")

        outline = pipeline.plan_layout(outline, request)
        add_breadcrumb("ai_pipeline", "layout planned")

        return outline
    except Exception as e:
        capture_exception(e, tags={"stage": "ai_pipeline", "topic": request.topic[:80]})
        return None  # any stage failing drops the WHOLE AI attempt — no partial outlines
