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

2. Visual theme — a color/font variant, picked independently and
   genuinely randomly (see backend/adapters/design/rule_based.py's
   _KNOWN_THEMES), since visual variety doesn't carry the same
   topic-fit risk narrative structure does.

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
    """Genuinely random — visual variety carries no topic-fit risk,
    unlike narrative structure. Callers that already have an explicit
    theme requested should skip this entirely."""
    return random.choice(THEME_VARIANT_IDS)
