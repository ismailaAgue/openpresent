"""
Quality Validator — spec Section 13 ("Quality Validation"), ADR-028.

Deterministic and $0, by design (Infrastructure Cost Policy, Section 7:
"prefer... deterministic rendering" over AI calls). Runs on EVERY
generated outline — document-derived or topic-derived, AI or
rule-based — before rendering, and auto-fixes what it safely can
without needing another AI round trip. What it can't fix
deterministically becomes a QualityReport issue, which the engine may
(optionally, config-gated) send to the AI pipeline's review_and_revise
for one bounded revision pass.

Checks implemented, mapped to spec Section 13's list:
  - duplicated slides           -> _find_duplicate_titles
  - repeated ideas               -> _dedupe_repeated_bullets (auto-fixed)
  - excessive bullets            -> _trim_excessive_bullets (auto-fixed)
  - empty sections                -> _find_empty_slides
  - weak conclusions              -> _ensure_closing_slide (auto-fixed)

Deliberately NOT attempted here (left as AI-review-only, or not
attempted at all for the MVP): "poor hierarchy," "inconsistent
terminology," and true layout-overflow detection (overflow is already
handled by python-pptx-side fitting logic in PptxExportAdapter, not
outline-level content). Same judgment call the Layout Classifier
already made for Quote/Case Study: a weak rule-based detector for a
genuinely hard-to-detect-with-rules issue is worse than not having it.
"""

from dataclasses import dataclass
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType
from backend.ports.ai_pipeline import QualityReport

MAX_BULLETS_PER_SLIDE = 6
CLOSING_TITLE_HINTS = (
    "thank", "question", "conclusion", "summary", "next steps", "wrap up", "contact"
)


def validate_and_fix(outline: Outline) -> tuple[Outline, QualityReport]:
    issues: list[str] = []
    auto_fixed: list[str] = []

    dup_titles = _find_duplicate_titles(outline)
    if dup_titles:
        issues.append(f"Duplicate slide titles: {', '.join(dup_titles)}")

    empty = _find_empty_slides(outline)
    if empty:
        issues.append(f"Slide(s) with no content: {', '.join(str(n) for n in empty)}")

    trimmed = _trim_excessive_bullets(outline)
    if trimmed:
        auto_fixed.append(f"Trimmed slides with more than {MAX_BULLETS_PER_SLIDE} bullets: "
                           f"{', '.join(str(n) for n in trimmed)}")

    deduped = _dedupe_repeated_bullets(outline)
    if deduped:
        auto_fixed.append(f"Removed {deduped} bullet(s) repeated verbatim elsewhere in the deck")

    added_closing = _ensure_closing_slide(outline)
    if added_closing:
        auto_fixed.append("Added a closing slide (deck ended without a summary/conclusion)")

    thin = _find_thin_content_slides(outline)
    if thin:
        issues.append(f"Slide(s) with very little content, may feel sparse: "
                       f"{', '.join(str(n) for n in thin)}")

    score = _score(outline, issues)
    return outline, QualityReport(score=score, issues=issues, auto_fixed=auto_fixed)


def _find_duplicate_titles(outline: Outline) -> list[str]:
    seen: dict[str, int] = {}
    dupes = []
    for s in outline.slides:
        key = s.title.strip().lower()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] == 2:
            dupes.append(s.title)
    return dupes


def _find_empty_slides(outline: Outline) -> list[int]:
    return [s.order for s in outline.slides if not any(
        b.text.strip() for b in s.content_blocks if b.type in (BlockType.BULLET, BlockType.NOTE)
    )]


def _find_thin_content_slides(outline: Outline) -> list[int]:
    """Non-title, non-closing slides with a single very short bullet
    and no speaker notes — likely to read as sparse/unfinished."""
    result = []
    for i, s in enumerate(outline.slides):
        if i == 0 or i == len(outline.slides) - 1:
            continue
        bullets = [b for b in s.content_blocks if b.type == BlockType.BULLET]
        notes = [b for b in s.content_blocks if b.type == BlockType.NOTE and b.text.strip()]
        if len(bullets) <= 1 and not notes:
            result.append(s.order)
    return result


def _trim_excessive_bullets(outline: Outline) -> list[int]:
    trimmed_slides = []
    for s in outline.slides:
        bullets = [b for b in s.content_blocks if b.type == BlockType.BULLET]
        if len(bullets) > MAX_BULLETS_PER_SLIDE:
            other = [b for b in s.content_blocks if b.type != BlockType.BULLET]
            s.content_blocks = bullets[:MAX_BULLETS_PER_SLIDE] + other
            trimmed_slides.append(s.order)
    return trimmed_slides


def _dedupe_repeated_bullets(outline: Outline) -> int:
    """Removes bullets whose (normalized) text already appeared on an
    earlier slide — a repeated idea restated later usually indicates
    the model padding content, not a deliberate callback."""
    seen: set[str] = set()
    removed = 0
    for s in outline.slides:
        kept: list[ContentBlock] = []
        for b in s.content_blocks:
            if b.type == BlockType.BULLET:
                key = b.text.strip().lower()
                if key and key in seen:
                    removed += 1
                    continue
                if key:
                    seen.add(key)
            kept.append(b)
        s.content_blocks = kept
    return removed


def _ensure_closing_slide(outline: Outline) -> bool:
    if not outline.slides:
        return False
    last = outline.slides[-1]
    if any(hint in last.title.lower() for hint in CLOSING_TITLE_HINTS):
        return False
    closing = Slide(
        order=last.order + 1,
        title="Thank You",
        content_blocks=[ContentBlock(type=BlockType.BULLET, text="Questions?")],
    )
    outline.slides.append(closing)
    return True


def _score(outline: Outline, issues: list[str]) -> float:
    """A coarse heuristic (0-10), not a precision metric — its job is
    only to signal 'looks roughly fine' vs 'worth a revision pass' to
    the engine and to surface in analytics/response headers."""
    score = 10.0
    score -= len(issues) * 1.2
    if len(outline.slides) < 3:
        score -= 2.0
    return max(0.0, round(score, 1))
