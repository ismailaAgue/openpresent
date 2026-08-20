"""
AI Pipeline Port — ADR-028 (AI-first pivot), substantially revised
ADR-030 (proper multi-stage pipeline + AI-driven layout planning).

ADR-030 supersedes ADR-028's cost-driven decision to collapse Planner/
Strategy/Outline/Content into one call, and DesignPort's "AI never
plans layout" rule — both per explicit product direction. What's
still true from ADR-028: every stage must degrade gracefully, and a
failure anywhere in the chain means the engine falls back to the
deterministic path, never a partially-AI, partially-broken deck.

Five real stages now, five real (potential) AI calls per generation:

  1. generate_strategy       — Planner + Strategy, given the request
                                and an optional Research brief
  2. generate_outline_structure — slide titles + one-line purpose only,
                                given the strategy (no content yet)
  3. generate_slide_content  — bullets + speaker notes, given the
                                outline structure (content generation
                                is still one call across all slides,
                                not one call per slide — N per-slide
                                calls would multiply latency/cost for
                                a batch of interdependent short outputs
                                that a single well-structured prompt
                                handles just as well; this is the one
                                place a deliberate batching choice
                                remains, clearly distinct from the old
                                "merge everything" approach)
  4. plan_layout              — AI now chooses each slide's layout_type
                                and image_query, given the actual
                                generated content (ADR-030 — supersedes
                                the old "AI never touches formatting"
                                rule). DesignPort's rule-based
                                classifier remains the deterministic
                                FALLBACK when this stage is unavailable
                                or fails, not removed.
  5. review_and_revise         — unchanged capability, now called by
                                default whenever the (also expanded,
                                see backend/validation/quality_validator.py)
                                deterministic review surfaces issues.
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
class ResearchBrief:
    """Output of the (optional) Research/Knowledge Expansion stage —
    see backend/ports/research.py. Empty facts is valid — Strategy
    generation works fine with none, just less grounded."""
    facts: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


@dataclass
class PresentationStrategy:
    narrative_style: str       # e.g. "Problem-Solution", "Chronological" — see pipeline/variety.py
    title_angle: str            # the specific angle/hook for the title slide
    key_themes: list[str] = field(default_factory=list)
    tone_notes: str = ""


@dataclass
class SlideOutlineItem:
    title: str
    purpose: str  # one line: what this slide needs to accomplish in the narrative


@dataclass
class QualityReport:
    score: float  # 0.0-10.0, heuristic — see backend/validation/quality_validator.py
    issues: list[str] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)


@dataclass
class SlideRegenerationContext:
    """ADR-038 — everything a single-slide regeneration needs, without
    requiring the full pipeline's PresentationStrategy to be persisted
    anywhere (it isn't — see engines/edit_slide.py's docstring for why
    that's fine). Assembled fresh from the stored Recipe each time."""
    topic_or_source_summary: str  # Recipe.source_text, truncated — "Topic: X" or document excerpt
    audience_type: str
    language: str
    other_slide_titles: list[str]  # every OTHER slide's title, for narrative consistency + no repeats
    current_title: str
    current_bullets: list[str]
    current_notes: str
    instructions: str | None = None  # user's freeform request, e.g. "make this more concise"


class AIPipelinePort(Protocol):
    def is_available(self) -> bool:
        """Cheap configuration/capacity check — must NOT make a network
        call. Individual stage methods degrade/raise on real failures;
        the engine catches and falls back to the deterministic path."""
        ...

    def generate_strategy(self, request: GenerationRequest,
                           research: ResearchBrief | None = None) -> PresentationStrategy:
        """Stage 1. Picks (or is nudged toward, see pipeline/variety.py)
        a narrative style and establishes the title angle and key
        themes the rest of the pipeline should follow."""
        ...

    def generate_outline_structure(self, request: GenerationRequest,
                                    strategy: PresentationStrategy) -> list[SlideOutlineItem]:
        """Stage 2. Slide titles + purpose only — no bullets, no notes
        yet. Must return exactly request.slide_count items."""
        ...

    def generate_slide_content(self, request: GenerationRequest, strategy: PresentationStrategy,
                                structure: list[SlideOutlineItem]) -> Outline:
        """Stage 3. Fills in bullets + speaker notes for every slide in
        `structure`, in order. Returns an Outline with
        structure_source=AI_GENERATED, layout_type left at the
        Slide model's default ('bullet_list') — Stage 4 sets it."""
        ...

    def plan_layout(self, outline: Outline, request: GenerationRequest) -> Outline:
        """Stage 4 (ADR-030). Assigns layout_type (one of bullet_list/
        statistics/comparison/process — the set the renderer actually
        supports) and image_query per slide, using the real generated
        content. Mutates and returns the same Outline."""
        ...

    def review_and_revise(self, outline: Outline, report: QualityReport,
                           request: GenerationRequest) -> Outline:
        """Stage 5. One bounded revision pass, given the deterministic
        quality validator's findings. Must preserve slide count, order,
        and each slide's layout_type — only content changes."""
        ...

    def regenerate_slide(self, context: SlideRegenerationContext) -> tuple[str, list[str], str]:
        """ADR-038, slide-level editing/partial regeneration. Given
        everything in `context`, produce a NEW (title, bullets, notes)
        for just this one slide — genuinely different from the current
        content (a regeneration that returns something near-identical
        to the input isn't useful), while staying consistent with
        `other_slide_titles` (don't duplicate another slide's topic)
        and honoring `instructions` if given. Returns a plain tuple
        rather than a Slide — this method never touches layout_type or
        image_query; the caller (engines/edit_slide.py) is responsible
        for deciding whether those need re-planning separately."""
        ...
