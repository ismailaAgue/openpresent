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

Every AI stage degrades gracefully within itself (a failed research
call just proceeds without research, for instance), but ADR-072
removed the old top-level safety net: previously, ANY failure
anywhere in the 4-call strategy/outline/content/layout chain (network
error, malformed JSON, provider outage, or simply no AI provider
configured at all) silently dropped the whole AI attempt back to a
fully generic, topic-blind deterministic template
(build_deterministic_outline, now deleted). That fallback was
explicitly the product's original "works with zero AI configured"
design principle — and it was also the direct cause of a real,
reported bug: decks whose closing slide (and often much more) kept
coming back as bland, generic filler whenever any single AI call
hiccuped. Topic-first generation is now AI-first in the strict sense:
no AI provider configured, or the pipeline failing even after ADR-070's
retries, raises AIGenerationUnavailableError instead of silently
degrading — a clear, surfaced failure the caller must handle, not a
silently worse deck.

ADR-070 — each of the 4 sequential calls in that chain still gets a
bounded retry (3 attempts, short exponential backoff) before this
raises — see _call_stage_with_retry. A single transient failure (a
rate limit, a momentary network blip) still doesn't have to throw away
3 other calls that already succeeded just because the 4th hiccuped
once — retries remain the right answer for a TRANSIENT failure; a
persistent one now surfaces honestly instead of masking as a
low-quality success.
"""

import os
import random
import time
import uuid
from typing import Callable
from backend.adapters import registry
from backend.models.recipe import Recipe, Theme
from backend.ports.ai_pipeline import GenerationRequest, QualityReport
from backend.ports.brand import BrandProfile
from backend.ports.export import UnsupportedFormatError
from backend.pipeline.variety import pick_theme_variant
from backend.adapters.design.rule_based import get_theme_variant
from backend.validation.quality_validator import validate_and_fix
from backend.monitoring.sentry_setup import capture_exception, add_breadcrumb


class AIGenerationUnavailableError(Exception):
    """ADR-072 — raised by topic-first generation when it can't produce
    a real, AI-generated deck: no AI provider is configured, or every
    retry attempt at some stage in the strategy/outline/content/layout
    chain still failed. Before this, either case silently fell back to
    a fully generic, topic-blind deterministic template instead of
    surfacing the problem — this exception is that surfacing. Callers
    (the API layer, the background worker) are expected to turn this
    into a clear, actionable failure for the person waiting on their
    deck, not to catch-and-retry into a lesser result."""

MAX_REVISION_PASSES = 1  # bounded — spec Section 13: "allow AN automatic improvement pass"

# ADR-040 — coarse stage labels reported to QueuePort.update_stage() as the
# pipeline runs, so the frontend can show real progress instead of a timer.
# Kept to 6 labels (not the full internal stage list) to match what's
# actually meaningful to show a user, not every internal function call.
STAGE_UNDERSTANDING = "understanding_request"
STAGE_OUTLINE = "building_outline"
STAGE_CONTENT = "generating_content"
STAGE_LAYOUT = "designing_slides"
STAGE_VISUALS = "selecting_visuals"
STAGE_DESIGN = "applying_design"


def _report(on_stage: Callable[[str], None] | None, stage: str) -> None:
    if on_stage is None:
        return
    try:
        on_stage(stage)
    except Exception as e:
        # Progress reporting is best-effort only — must never break or
        # slow down an otherwise-successful generation.
        capture_exception(e, tags={"stage": "progress_report"})


STAGE_RETRY_ATTEMPTS = 3  # the call itself, plus up to 2 retries
STAGE_RETRY_BASE_DELAY = 1.0  # seconds; doubles each retry (1s, 2s)


def _call_stage_with_retry(fn: Callable, *args, stage_name: str, **kwargs):
    """A single transient failure — a provider rate limit, a momentary
    network blip, one malformed-JSON response — at ANY ONE of this
    pipeline's 4 sequential AI calls used to be enough to discard the
    ENTIRE AI-generated deck: _run_ai_pipeline's outer try/except
    catches everything and returns None, and the caller then falls all
    the way back to build_deterministic_outline's fully generic,
    topic-blind template — hardcoded "Thank You" / "Questions?"
    closing slide chief among the obviously-generic tells, but really
    every slide in that fallback is equally generic, not just the
    last one. This was a real, reported pattern ("keeps returning
    Thank You"), not a hypothetical: with zero retries anywhere in the
    AI adapter layer, a rate-limited account or a flaky provider would
    turn almost every generation into the bland fallback, even though
    3 of the 4 calls in the chain may have already succeeded.

    Retrying the ONE failing call, a bounded few times with a short
    backoff, before giving up on the whole pipeline, means a single
    transient hiccup no longer throws away calls that already
    succeeded. This can't distinguish a genuinely transient error
    (worth retrying) from a hard one — bad API key, provider fully
    down, consistently malformed output (not worth retrying, will just
    fail the same way 3 times) — since the AI Port abstracts over
    several providers with different exception shapes; that's a stated
    simplification, not a claim of correctness. A hard failure just
    takes a few extra seconds to reach the same, already-correct
    deterministic fallback it would have reached immediately before —
    strictly better for the transient case, never worse for the
    already-failing one."""
    last_exc: Exception | None = None
    for attempt in range(STAGE_RETRY_ATTEMPTS):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < STAGE_RETRY_ATTEMPTS - 1:
                add_breadcrumb("ai_pipeline", f"{stage_name} failed, retrying",
                                data={"attempt": attempt + 1, "error": str(e)[:200]})
                time.sleep(STAGE_RETRY_BASE_DELAY * (2 ** attempt))
    raise last_exc


def generate_presentation_from_topic(
    topic: str,
    slide_count: int = 10,
    audience_type: str = "general",
    language: str = "en",
    tone: str = "professional",
    export_format: str = "pptx",
    project_id: str | None = None,
    on_stage: Callable[[str], None] | None = None,
    brand: BrandProfile | None = None,  # ADR-045 — optional, purely additive
) -> tuple[Recipe, bytes, QualityReport]:
    if not topic or not topic.strip():
        raise ValueError("topic must not be empty")

    project_id = project_id or str(uuid.uuid4())
    request = GenerationRequest(
        topic=topic.strip(), slide_count=slide_count,
        audience_type=audience_type, language=language, tone=tone,
        brand=brand, export_format=export_format,  # ADR-054
    )

    _report(on_stage, STAGE_UNDERSTANDING)
    outline = _run_ai_pipeline(request, on_stage)  # raises AIGenerationUnavailableError, never returns None now
    ai_layout_planned = True  # only reachable when the AI pipeline actually succeeded

    _report(on_stage, STAGE_VISUALS)
    outline, quality_report = validate_and_fix(outline, export_format=export_format, language=request.language)

    pipeline = registry.get_ai_pipeline_adapter()
    if pipeline.is_available() and quality_report.issues:
        for _ in range(MAX_REVISION_PASSES):
            if not quality_report.issues:
                break
            try:
                revised = pipeline.review_and_revise(outline, quality_report, request)
                outline, quality_report = validate_and_fix(revised, export_format=export_format, language=request.language)
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
    _report(on_stage, STAGE_DESIGN)
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


def _run_ai_pipeline(request: GenerationRequest, on_stage: Callable[[str], None] | None = None):
    """Runs Research (optional) -> Strategy -> Outline Structure ->
    Slide Content -> Layout Planning as one all-or-nothing attempt.
    Returns a fully-formed Outline with layout_type/image_query already
    set. ADR-072 — no longer returns None on failure; raises
    AIGenerationUnavailableError instead, whether the cause is no AI
    provider configured at all, or every retry attempt at some stage
    still failing. There is no more "callers treat this as a signal to
    fall back" — a caller either gets a real outline or an exception,
    nothing in between."""
    pipeline = registry.get_ai_pipeline_adapter()
    if not pipeline.is_available():
        raise AIGenerationUnavailableError(
            "No AI provider is configured. Topic-based generation requires "
            "a configured AI provider (set an API key for a supported "
            "provider) — it can no longer fall back to a generic template."
        )

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
        strategy = _call_stage_with_retry(pipeline.generate_strategy, request, research_brief,
                                           stage_name="generate_strategy")
        add_breadcrumb("ai_pipeline", "strategy generated",
                        data={"narrative_style": strategy.narrative_style})

        _report(on_stage, STAGE_OUTLINE)
        structure = _call_stage_with_retry(pipeline.generate_outline_structure, request, strategy,
                                            stage_name="generate_outline_structure")
        add_breadcrumb("ai_pipeline", "outline structure generated", data={"slides": len(structure)})

        _report(on_stage, STAGE_CONTENT)
        outline = _call_stage_with_retry(pipeline.generate_slide_content, request, strategy, structure,
                                          stage_name="generate_slide_content")
        add_breadcrumb("ai_pipeline", "slide content generated")

        _report(on_stage, STAGE_LAYOUT)
        outline = _call_stage_with_retry(pipeline.plan_layout, outline, request,
                                          stage_name="plan_layout")
        add_breadcrumb("ai_pipeline", "layout planned")

        return outline
    except Exception as e:
        capture_exception(e, tags={"stage": "ai_pipeline", "topic": request.topic[:80]})
        # Every stage already retried (_call_stage_with_retry) before
        # reaching here — this is a genuinely persistent failure, not a
        # transient one, so it surfaces as-is rather than being masked.
        raise AIGenerationUnavailableError(
            f"AI generation failed after retries: {e}"
        ) from e
