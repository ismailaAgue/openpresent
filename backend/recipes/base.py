"""
Recipe — Phase 3.5 Step 2.

A Recipe controls how a classified document gets turned into slides:
information density (bullets per slide), the closing slide's purpose,
and a canonical section order to present sections in even if the
source document listed them differently (e.g. a resume with Education
before Experience still presents Experience first, since that's the
conventional, more useful order for a presentation).

This is intentionally a plain data object, not behavior — the
Structure Engine reads a Recipe's values and applies them; the Recipe
itself doesn't do any parsing or text manipulation.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Recipe:
    max_bullets_per_slide: int
    closing_slide_title: str
    # Lowercase keywords, in presentation order. A section whose heading
    # contains one of these is moved to that position; unmatched
    # sections keep their original relative order, appended after all
    # matched ones.
    canonical_section_order: tuple[str, ...] = field(default_factory=tuple)
