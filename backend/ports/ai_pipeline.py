"""
AI Pipeline Port — ADR-028 (AI-first pivot).

The original AIPort (backend/ports/ai.py) enhances a rule-based baseline
derived from an uploaded document. This port covers the new, separate
capability: generating a presentation directly from a topic, with no
source document at all — the "enter a topic, get a deck" flow.

Same discipline as every other port in this codebase:
- is_available() is a cheap capacity check, never a network call.
- Every method must degrade gracefully. Callers (backend/engines/
  ai_generate.py) treat any failure or empty result as "fall back to
  the deterministic topic template" (backend/pipeline/
  deterministic_topic_outline.py) — the AI-optional guarantee
  (Constitution Principle 3) applies here exactly as it does to the
  document-upload path.

Deliberately two methods, not five separate pipeline-stage calls
(Planner / Strategy / Outline / Content / Layout / Image / Review as
individually round-tripped AI calls). Layout and image-query
assignment already have a good, deterministic, zero-cost home in
DesignPort (backend/adapters/design/rule_based.py) per the product
decision that "AI should never directly control formatting" — so
those stages are never AI calls at all. Planner, Strategy, Outline,
and Content are combined into a single generate_presentation_outline()
call: separate round trips would multiply latency and free-tier quota
usage for no quality benefit, and the Infrastructure Cost Policy is
explicit that avoiding unnecessary paid/rate-limited API calls beats
mirroring the conceptual pipeline diagram call-for-call. The seam to
split this into multiple calls later (e.g. a dedicated Research stage)
is still here — it's a new method on this Protocol, not a rewrite.
"""

from dataclasses import dataclass, field
from typing import Protocol
from backend.models.recipe import Outline


@dataclass
class GenerationRequest:
    topic: str
    slide_count: int = 10
    audience_type: str = "general"
    language: str = "en"
    tone: str = "professional"


@dataclass
class QualityReport:
    score: float  # 0.0-10.0, heuristic — see backend/validation/quality_validator.py
    issues: list[str] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)


class AIPipelinePort(Protocol):
    def is_available(self) -> bool:
        """Cheap configuration/capacity check (e.g. is an API key
        present) — must NOT make a network call. Individual methods
        are responsible for degrading gracefully if the provider
        turns out to be unreachable at call time."""
        ...

    def generate_presentation_outline(self, request: GenerationRequest) -> Outline:
        """Planner + Strategy + Outline + per-slide Content Generation,
        collapsed into one structured call. Must return an Outline with
        structure_source=AI_GENERATED and exactly request.slide_count
        slides (or raise — callers fall back to the deterministic
        template on any exception, never on a silently-wrong slide
        count). Each slide's content_blocks should include BULLET
        blocks (key points) and a NOTE block (speaker notes)."""
        ...

    def review_and_revise(self, outline: Outline, report: QualityReport,
                           request: GenerationRequest) -> Outline:
        """One bounded revision pass, given the deterministic quality
        validator's findings (backend/validation/quality_validator.py).
        Must preserve slide count and order; only content should change.
        Optional capability — the engine only calls this when AI is
        available AND OPENPRESENT_AI_QUALITY_REVIEW=true (Cost Policy:
        the deterministic validator already auto-fixes what it safely
        can for $0; this is the more expensive narrative-level pass)."""
        ...
