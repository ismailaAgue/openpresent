"""
Layout Classifier — Phase 3.5 Step 4 (ADR-022, extended ADR-023).

Per-slide (not per-document, unlike DocumentClassifier) rule-based
detection of which slides would benefit from a specialized visual
layout instead of a plain bullet list. Three layout types implemented
so far — Statistics, Comparison, and Process/Timeline — each fully
tested against real generated output. Quote and Case Study remain
deliberately deferred: detecting them reliably with pure rules is
meaningfully harder (a "quote" needs to be distinguished from any
other quoted phrase; a "case study" has no reliable structural
signal the way numbers or "vs" do), and shipping a weak detector
just to hit a round number would be worse than not having the layout.

This never touches slide CONTENT — only decides how it should be
drawn. Content decisions belong to the Structure Engine (ADR-020);
this belongs to the Design Engine, per the Blueprint's separation of
"what content" from "how it looks."
"""

import re
from backend.models.recipe import Slide

STATISTIC_PATTERN = re.compile(
    r"(\$[\d,.]+[MKB]?\b|\b\d{1,3}(,\d{3})*(\.\d+)?%|\b\d+(\.\d+)?%|\$\d)"
)
MAX_STAT_BULLET_LENGTH = 60
MIN_STATS_FOR_LAYOUT = 2
COMPARISON_PATTERN = re.compile(r"\b(vs\.?|versus)\b", re.IGNORECASE)

PROCESS_TITLE_PATTERN = re.compile(
    r"\b(timeline|process|steps|stages|roadmap|workflow|phases)\b", re.IGNORECASE
)
# Sequential ordinal/step markers at the START of a bullet — a strong
# signal the content is meant to be read in order, not as a flat list.
PROCESS_BULLET_PATTERN = re.compile(
    r"^(first|second|third|fourth|fifth|then|next|finally|lastly|"
    r"step\s*\d+|stage\s*\d+|phase\s*\d+)\b", re.IGNORECASE
)
MIN_SEQUENTIAL_BULLETS = 2


def classify_layout(slide: Slide) -> str:
    """Returns 'comparison', 'process', 'statistics', or 'bullet_list'
    (default). Comparison and process are checked before statistics —
    both are stronger, more deliberate signals (an explicit title cue,
    or explicit sequencing language) than an incidental cluster of
    numbers, so they take priority when a slide could match more than
    one pattern."""
    if _is_comparison_slide(slide):
        return "comparison"
    if _is_process_slide(slide):
        return "process"
    if _is_statistics_slide(slide):
        return "statistics"
    return "bullet_list"


def _is_comparison_slide(slide: Slide) -> bool:
    return bool(COMPARISON_PATTERN.search(slide.title))


def _is_process_slide(slide: Slide) -> bool:
    if PROCESS_TITLE_PATTERN.search(slide.title):
        return True
    bullets = [b for b in slide.content_blocks if b.text]
    sequential_count = sum(1 for b in bullets if PROCESS_BULLET_PATTERN.match(b.text.strip()))
    return sequential_count >= MIN_SEQUENTIAL_BULLETS


def _is_statistics_slide(slide: Slide) -> bool:
    bullets = [b for b in slide.content_blocks if b.text]
    if len(bullets) < MIN_STATS_FOR_LAYOUT:
        return False
    stat_like_count = sum(
        1 for b in bullets
        if STATISTIC_PATTERN.search(b.text) and len(b.text) <= MAX_STAT_BULLET_LENGTH
    )
    # Require a clear majority of the slide's bullets to be stat-like —
    # one number mentioned in passing in an otherwise normal bullet
    # list shouldn't flip the whole slide into a statistics layout.
    return stat_like_count >= MIN_STATS_FOR_LAYOUT and stat_like_count >= len(bullets) * 0.6
