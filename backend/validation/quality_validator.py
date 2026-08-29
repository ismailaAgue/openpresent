"""
Quality Validator — spec Section 13 ("Quality Validation"), ADR-028,
expanded ADR-030 ("build the quality review properly").

Deterministic and $0, by design (Infrastructure Cost Policy, Section 7:
"prefer... deterministic rendering" over AI calls). Runs on EVERY
generated outline — document-derived or topic-derived, AI or
rule-based — before rendering, and auto-fixes what it safely can
without needing another AI round trip. What it can't fix
deterministically becomes a QualityReport issue, which the engine
sends to the AI pipeline's review_and_revise (now a default part of
the pipeline, not opt-in — see backend/engines/ai_generate.py) for one
bounded revision pass whenever real issues remain.

Checks implemented, mapped to spec Section 13's list:
  - duplicated slides           -> _find_duplicate_titles
  - repeated ideas               -> _dedupe_repeated_bullets (auto-fixed)
  - excessive bullets            -> _trim_excessive_bullets (auto-fixed)
  - empty sections                -> _find_empty_slides
  - weak conclusions              -> _ensure_closing_slide (auto-fixed)
  - poor hierarchy (ADR-030)     -> _find_poor_hierarchy (paragraph-as-bullet)
  - inconsistent terminology (ADR-030) -> _find_inconsistent_terminology
  - layout overflow risk (ADR-030)     -> _find_overflow_risk

ADR-030 note on the two checks ADR-028 originally deferred as "too
hard to detect reliably with rules": both are now implemented as
genuinely useful heuristics rather than attempts at full correctness.
Neither claims precision — "inconsistent terminology" flags candidate
term variants for a human (or the AI revision pass) to judge, it
doesn't silently rewrite anything, since an automated rewrite risking
a false positive is worse than a flagged-but-unfixed true positive
here. "Overflow risk" is a heuristic total-character budget per
layout type, not a measurement of actual rendered text extent (the
renderer's own font-fitting logic, unchanged, still has final say over
what actually ships) — it exists to feed the AI revision pass a signal
worth acting on, not to be authoritative on its own.
"""

from dataclasses import dataclass
from collections import defaultdict
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType
from backend.ports.ai_pipeline import QualityReport

MAX_BULLETS_PER_SLIDE = 6
CLOSING_TITLE_HINTS = (
    "thank", "question", "conclusion", "summary", "next steps", "wrap up", "contact"
)


def validate_and_fix(outline: Outline, export_format: str = "pptx") -> tuple[Outline, QualityReport]:
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

    hierarchy_issues = _find_poor_hierarchy(outline) if export_format not in ("document_docx", "document_pdf") else []
    # ADR-054 — "paragraph-length bullet" is a deck-specific defect (a
    # slide bullet SHOULD be short; a paragraph in that role means
    # something's wrong). For document_docx, multi-sentence paragraphs
    # are the intended, correctly-generated content (see json_pipeline_
    # base.py's format-aware content prompt) — flagging them here would
    # feed a false "problem" straight into the AI revision pass, which
    # would then dutifully shrink real prose back into fragments,
    # undoing the whole point of generating prose in the first place.
    if hierarchy_issues:
        issues.append(f"Slide(s) with a paragraph-length bullet (poor hierarchy, consider "
                       f"splitting into separate points): {', '.join(str(n) for n in hierarchy_issues)}")

    terminology_issues = _find_inconsistent_terminology(outline)
    if terminology_issues:
        issues.append("Possibly inconsistent terminology (same term used with different "
                       "capitalization/spelling): " + "; ".join(terminology_issues))

    # ADR-054 — "overflow risk" is a per-layout character budget
    # specifically about whether text will visually fit a FIXED slide
    # region (see this module's own docstring on the check). A
    # scrolling Word document has no such fixed region — the check is
    # structurally meaningless for document_docx, not just usually
    # a non-issue, so it's skipped outright rather than just often
    # scoring clean.
    overflow_risk = _find_overflow_risk(outline) if export_format not in ("document_docx", "document_pdf") else []
    if overflow_risk:
        issues.append(f"Slide(s) with enough combined text that they may feel crowded for "
                       f"their layout: {', '.join(str(n) for n in overflow_risk)}")

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


# -- ADR-030 additions: previously-deferred checks, now implemented -----

POOR_HIERARCHY_CHAR_THRESHOLD = 200  # a bullet this long reads as a paragraph, not a point

# Layout-specific rough character budgets — heuristic only, not a
# measurement of actual rendered extent (the renderer's own
# font-fitting logic has final say). Comparison/process slides are
# split across multiple columns/steps so each can hold more text
# overall before feeling crowded than a single-column bullet_list can.
OVERFLOW_BUDGET_BY_LAYOUT = {
    "bullet_list": 420,
    "statistics": 260,
    "comparison": 600,
    "process": 520,
}


def _find_poor_hierarchy(outline: Outline) -> list[int]:
    result = []
    for s in outline.slides:
        for b in s.content_blocks:
            if b.type == BlockType.BULLET and len(b.text) > POOR_HIERARCHY_CHAR_THRESHOLD:
                result.append(s.order)
                break
    return result


def _find_inconsistent_terminology(outline: Outline) -> list[str]:
    """Groups every capitalized multi-character token by its lowercase
    form; if a lowercase form maps to more than one distinct surface
    form used more than once total across the deck, it's flagged as a
    possible inconsistency (e.g. "AI" and "Ai" and "A.I." all mapping
    to the same normalized key). Deliberately conservative: common
    words that are legitimately capitalized only at sentence-start are
    excluded by requiring the term to appear standalone (not just as
    the first word of its bullet) at least once."""
    variants_by_key: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in outline.slides:
        for b in s.content_blocks:
            if b.type != BlockType.BULLET:
                continue
            words = b.text.split()
            for i, word in enumerate(words):
                cleaned = word.strip(".,;:!?()[]\"'")
                if len(cleaned) < 2 or not any(c.isalpha() for c in cleaned):
                    continue
                if not cleaned[0].isupper():
                    continue
                if i == 0:
                    continue  # sentence-initial capitalization isn't a terminology signal
                key = cleaned.lower()
                variants_by_key[key][cleaned] += 1

    flagged = []
    for key, variants in variants_by_key.items():
        if len(variants) > 1 and sum(variants.values()) > 1:
            surface_forms = ", ".join(sorted(variants.keys()))
            flagged.append(f"\"{surface_forms}\"")
    return flagged[:5]  # cap — this is a hint, not an exhaustive audit


def _find_overflow_risk(outline: Outline) -> list[int]:
    result = []
    for s in outline.slides:
        budget = OVERFLOW_BUDGET_BY_LAYOUT.get(s.layout_type or "bullet_list", 420)
        total_chars = sum(
            len(b.text) for b in s.content_blocks if b.type == BlockType.BULLET
        )
        if total_chars > budget:
            result.append(s.order)
    return result
