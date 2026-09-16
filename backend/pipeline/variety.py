"""
Presentation variety — ADR-030, spec Section 10 ("the same prompt
should not always generate identical presentations").

Two independent axes of variety:

1. Narrative structure — a catalog of named styles, one of which the
   AI's Strategy stage (Stage 1, backend/adapters/ai/json_pipeline_base.py)
   is asked to pick, given a RANDOMLY suggested starting candidate it's
   free to override if a different style genuinely fits the topic
   better. This is deliberately AI-in-the-loop, not purely random
   selection — a random style badly mismatched to the topic (e.g.
   "Chronological" forced onto a deck that has no timeline) would hurt
   quality for the sake of variety, which the Quality Philosophy
   (spec Section 1) explicitly says should never happen.

2. Visual theme — a color/font variant, picked independently (see
   backend/adapters/design/rule_based.py's _KNOWN_THEMES). ADR-071 —
   no longer a flat uniform random pick across all 9 variants:
   editorial_cream is now weighted heavily as the de facto default
   (see pick_theme_variant), a deliberate product decision, while the
   others remain reachable for genuine variety.

For the deterministic (no-AI) fallback path
(backend/pipeline/deterministic_topic_outline.py), narrative style
selection doesn't apply — there's no AI making structural choices — but
theme variety still does, so a deck generated with no AI configured
still doesn't look identical to the last no-AI deck.
"""

import random

NARRATIVE_STYLES = [
    {
        "id": "classic_narrative",
        "name": "Classic Narrative",
        "description": "Straightforward intro -> body sections -> conclusion. The safe, "
                        "reliable default for most factual or informational topics.",
    },
    {
        "id": "problem_solution",
        "name": "Problem-Solution",
        "description": "Establish a problem or pain point, build its impact, then present "
                        "the solution and next steps. Strong fit for pitches, proposals, "
                        "and topics with a clear challenge to address.",
    },
    {
        "id": "story_driven",
        "name": "Story-Driven",
        "description": "A narrative arc with a beginning, a turning point, and a resolution. "
                        "Fits topics with a real chronological or causal story to tell.",
    },
    {
        "id": "data_driven",
        "name": "Data-Driven",
        "description": "Leads with key statistics/metrics, builds an argument from evidence "
                        "outward. Fits topics that are fundamentally about numbers or trends.",
    },
    {
        "id": "chronological",
        "name": "Chronological",
        "description": "Strict timeline ordering, era by era or step by step through time. "
                        "Fits historical or process-over-time topics.",
    },
    {
        "id": "comparative",
        "name": "Comparative",
        "description": "Structured around comparing two or more things — options, eras, "
                        "approaches, sides of a debate. Fits inherently comparative topics.",
    },
]

THEME_VARIANT_IDS = [
    "default", "academic", "warm", "modern_dark",
    # ADR-059
    "gradient_violet", "minimal_mono", "bold_violet_stats", "clean_saas_blue",
    # ADR-062
    "editorial_cream",
]


def suggest_style() -> dict:
    """A random suggestion, NOT a mandate — the AI strategy prompt is
    explicitly told it can override this if the topic calls for a
    different style. This just breaks the tendency of a model to
    default to the same 'safe' style every time absent any nudge."""
    return random.choice(NARRATIVE_STYLES)


def pick_theme_variant() -> str:
    """ADR-071 — editorial_cream is now the dominant default for
    topic-first generation: a direct, explicit product decision
    (a real reference deck's design was preferred outright over the
    prior spread of 9 equally-likely themes), not an incidental
    side-effect of this function. Weighted heavily toward
    editorial_cream rather than switched to it outright — the other 8
    variants remain real, reachable options (a person can still land
    on one, or explicitly request one), preserving SOME of what
    ADR-030's original variety mechanism was for, while making the
    editorial aesthetic what most generations actually look like,
    matching the explicit "I want it to be like this from now on"
    direction. 75% is a stated, roughly-chosen weight — there was no
    request for an exact number, and 100% would have quietly deleted 8
    themes' worth of working functionality no one asked to remove."""
    if random.random() < 0.75:
        return "editorial_cream"
    return random.choice([v for v in THEME_VARIANT_IDS if v != "editorial_cream"])
