"""
Rule-based Structure Engine adapter — Technical Blueprint Section 3.2 / 9.

This is the DEFAULT and must be genuinely usable on its own, with zero
AI involvement (Constitution Principle 1, 15). It implements heading
detection and paragraph-based splitting, plus one known narrative shape
for the student wedge, per Blueprint Section 3 ("Story Architect folded
into Planner for v1").

Revision (ADR-017): fixed against a real resume-style document copied
from an AI chat tool, which exposed three distinct bugs: (1) markdown
bold headers ("**SECTION**") weren't recognized as headings at all,
so every content slide fell back to a generic repeated "Overview"
label; (2) an AI-generated "how to use this" instructional footer got
included as if it were real presentation content; (3) wrapped lines
and markdown bullet points ("- point one") were joined with no space
and no bullet-boundary awareness, producing run-on, jammed-together
text ("recordof", "resourcesto"). All three are fixed below.

Revision (Phase 3.5 Step 2): document classification + type-specific
recipes. The engine now classifies the document (resume, academic,
business, lecture, general) and uses a Recipe to control bullet
density, the closing slide's purpose, and canonical section ordering —
replacing the old single-purpose resume-keyword check that only
affected the closing slide with a general mechanism that shapes the
whole deck.
"""

import re
from backend.ports.structure import StructurePort
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.models.document_type import DocumentType
from backend.classifier.document_classifier import DocumentClassifier
from backend.recipes.base import Recipe
from backend.recipes.registry import get_recipe

MAX_BULLETS_PER_SLIDE = 5
# Revision (ADR-027): MAX_BULLET_LENGTH was 140 — real generated output
# showed sentences getting hard-cut mid-thought with an ellipsis
# ("achieving $15M in annual synergies within 12…"), which reads as
# broken, not designed. Bullets now wrap across lines (word_wrap=True
# on every text box that renders them) instead of being truncated.
# BULLET_SAFETY_CEILING remains only to stop a truly pathological
# run-on sentence from breaking a slide's layout — it should almost
# never actually trigger for normal prose.
BULLET_SAFETY_CEILING = 400
MAX_TITLE_LENGTH = 60
THIN_CONTENT_WORD_THRESHOLD = 40  # below this, don't pad into a fake multi-slide structure

# Section headers come in several real-world shapes: markdown "#"
# headers, numbered headings, markdown bold ("**HEADER**", optionally
# with a trailing colon), and ALL-CAPS short lines (extremely common
# in resumes: "EDUCATION", "CORE COMPETENCIES"). These are matched by
# regex because they're structurally unambiguous. Plain Title-Case
# lines are NOT matched by regex alone (see _looks_like_heading below)
# — a naive "starts with a capital letter" pattern also matches full
# prose sentences like "Dynamic and results-driven Marketing Manager
# with over 8 years of experience", which is a sentence, not a heading.
_HEADING_PATTERN = re.compile(
    r"^(#{1,3}\s*.+"
    r"|[0-9]+[\.\)]\s*.+"
    r"|\*\*[^*]{2,80}\*\*:?\s*$"
    r"|[A-Z][A-Z0-9 &\-]{2,60})$"
)

# Small connector words don't need to be capitalized in real Title Case
# headings ("Core Competencies" is fine even without capitalizing "and").
_TITLE_CASE_CONNECTORS = {
    "a", "an", "the", "of", "in", "and", "or", "with", "for", "to",
    "on", "at", "by", "from",
}


def _looks_like_title_case_heading(line: str) -> bool:
    """A real heading (e.g. 'Core Competencies', 'Work Experience') is
    short and has most of its significant words capitalized. A full
    sentence that merely starts with a capital letter (e.g. 'Dynamic
    and results-driven Marketing Manager with over 8 years of
    experience') is NOT a heading, even though a naive regex would
    match it — this check distinguishes the two."""
    if len(line) > 50 or len(line) < 3:
        return False
    if not line[0].isupper():
        return False
    if re.search(r"[.!?,;:]", line):  # real sentences carry punctuation; headings don't
        return False
    words = line.split()
    if len(words) < 1 or len(words) > 7:  # headings are short phrases, not long sentences
        return False
    significant = [w for w in words if w.lower() not in _TITLE_CASE_CONNECTORS]
    if not significant:
        return False
    capitalized = sum(1 for w in significant if w[0].isupper())
    return capitalized / len(significant) >= 0.8

# A line of three or more dashes/underscores/equals is a plain visual
# separator, not content — drop it entirely rather than treating it as
# either a heading or a bullet.
_SEPARATOR_LINE = re.compile(r"^[\-_=]{3,}$")

# Lines that are clearly instructions written for a human reader, not
# presentation content — e.g. AI-chat-tool output that includes a
# "here's how to turn this into slides" footer. Matched on the
# beginning of a paragraph/section body, case-insensitive.
_INSTRUCTIONAL_TEXT_PATTERNS = re.compile(
    r"^(how to use this|paste this into|suggested \d+-slide|"
    r"here is a suggested|copy this into|use the bolded headers)",
    re.IGNORECASE,
)

# Bullet-list markers at the start of a line — "- ", "* ", "• ", "1. ".
_BULLET_MARKER = re.compile(r"^\s*([\-*•]|[0-9]+[\.\)])\s+")


def _smart_truncate(text: str, max_len: int) -> str:
    """Truncate at the last word boundary before max_len, never mid-word.
    Only appends '…' if something was actually cut."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    last_space = cut.rfind(" ")
    if last_space > 0:
        cut = cut[:last_space]
    return cut.rstrip(",;: ") + "…"


def _strip_markdown_decoration(text: str) -> str:
    """Remove leftover markdown symbols (bold **, stray asterisks) that
    shouldn't appear as literal characters in presented text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold** -> bold
    text = text.replace("**", "").replace("*", "")
    return text.strip()


def _is_instructional(text: str) -> bool:
    return bool(_INSTRUCTIONAL_TEXT_PATTERNS.match(text.strip()))


class RuleBasedStructureAdapter(StructurePort):
    def __init__(self):
        self._classifier = DocumentClassifier()

    def build_outline(self, source_text: str, audience_type: str) -> Outline:
        text = source_text.strip()
        if not text:
            raise ValueError("source_text must not be empty")

        sections = self._split_into_sections(text)
        # Drop any section whose heading OR body reads as instructions
        # to a human rather than real content (Bug #2 from real-world
        # testing) — this must happen before deciding which path to
        # take, since a document that's otherwise well-headed shouldn't
        # have its content-detection judged by a footer that isn't content.
        sections = [
            (h, b) for h, b in sections
            if not _is_instructional(h) and not _is_instructional(b)
        ]

        # Classify using whatever headings were actually detected —
        # a real heading match is a much stronger signal than body text
        # alone (see DocumentClassifier), so this reuses the parsing
        # work already done above rather than re-scanning blind.
        document_type = self._classifier.classify(text, headings=[h for h, _ in sections])
        recipe = get_recipe(document_type)

        if len(sections) == 0:
            slides = self._known_shape_fallback(text, recipe)
        else:
            sections = self._reorder_sections(sections, recipe)
            slides = self._slides_from_sections(sections, recipe)

        return Outline(
            structure_source=StructureSource.RULE_BASED,
            slides=slides,
            document_type=document_type.value,
        )

    # -- internals -----------------------------------------------------

    def _reorder_sections(self, sections: list[tuple[str, str]],
                           recipe: Recipe) -> list[tuple[str, str]]:
        """Reorder sections[1:] to match the recipe's canonical order
        (e.g. Experience before Education for a resume, regardless of
        the source document's own ordering). sections[0] is always left
        in place — it's the document's actual title/opening section,
        not something a recipe should reshuffle."""
        if not recipe.canonical_section_order or len(sections) <= 1:
            return sections

        head, rest = sections[0], sections[1:]

        def sort_key(section: tuple[str, str]) -> int:
            heading_lower = section[0].lower()
            for i, keyword in enumerate(recipe.canonical_section_order):
                if keyword in heading_lower:
                    return i
            return len(recipe.canonical_section_order)  # unmatched -> keep at the end

        # Stable sort: unmatched sections (all sharing the same "end"
        # key) preserve their original relative order among themselves.
        reordered_rest = sorted(rest, key=sort_key)
        return [head] + reordered_rest

    def _split_into_sections(self, text: str) -> list[tuple[str, str]]:
        """Return list of (heading, body) pairs based on detected headings.
        Wrapped lines within a section are joined with spaces (they're
        fragments of the same flowing text, not separate items), while
        genuine bullet-marker lines are kept on their own line so
        _chunk_body can split on them explicitly."""
        lines = text.split("\n")
        sections: list[tuple[str, list[str]]] = []
        current_heading = None
        current_body: list[str] = []

        in_instructional_footer = False
        for raw_line in lines:
            line = raw_line.strip()
            if not line or _SEPARATOR_LINE.match(line):
                continue
            if (_HEADING_PATTERN.match(line) and len(line) < 90) or _looks_like_title_case_heading(line):
                if current_heading is not None:
                    sections.append((current_heading, current_body))
                current_heading = _strip_markdown_decoration(
                    re.sub(r"^#{1,3}\s*|^[0-9]+[\.\)]\s*", "", line).rstrip(":")
                )
                current_body = []
                in_instructional_footer = False
                continue
            if _is_instructional(line):
                # An instructional footer line ends the real content for
                # this section — everything from here until the next
                # genuine heading is AI-tool guidance-to-a-human, not
                # presentation content, so stop collecting body lines.
                in_instructional_footer = True
                continue
            if not in_instructional_footer:
                current_body.append(line)

        if current_heading is not None:
            sections.append((current_heading, current_body))

        joined_sections = []
        for h, body_lines in sections:
            joined = self._rejoin_lines(body_lines)
            joined_sections.append((h, joined))

        # A genuine section heading is followed by real content. A
        # detected "heading" with an empty body (e.g. "Boston
        # University" sitting alone on its own line — a proper noun,
        # not a section label) is almost always a false positive from
        # the title-case heuristic. Merge it back into the previous
        # section's body instead of leaving a near-empty phantom slide.
        # The very first section is exempt: a genuinely empty body
        # there just means "this document's title has no separate
        # intro," which is normal and handled elsewhere.
        cleaned: list[tuple[str, str]] = []
        for i, (h, b) in enumerate(joined_sections):
            if i > 0 and not b.strip() and cleaned:
                prev_h, prev_b = cleaned[-1]
                cleaned[-1] = (prev_h, (prev_b + "\n" + h) if prev_b else h)
            else:
                cleaned.append((h, b))
        return cleaned

    def _rejoin_lines(self, lines: list[str]) -> str:
        """Reconstruct a body from raw lines: bullet-marker lines each
        start a new logical item (joined with '\\n' so _chunk_body can
        split on them); consecutive plain prose lines are word-wrapped
        fragments of one sentence and are joined with a space so words
        never collide (fixes 'recordof'-style artifacts)."""
        pieces: list[str] = []
        for line in lines:
            line = _strip_markdown_decoration(line)
            if not line:
                continue
            if _BULLET_MARKER.match(line) or not pieces:
                pieces.append(line)
            else:
                pieces[-1] = pieces[-1] + " " + line
        return "\n".join(pieces)

    def _slides_from_sections(self, sections: list[tuple[str, str]], recipe: Recipe) -> list[Slide]:
        slides: list[Slide] = []
        doc_title = sections[0][0]
        slides.append(self._title_slide(doc_title))
        order = 2
        for idx, (heading, body) in enumerate(sections):
            if idx == 0 and heading == doc_title and not body.strip():
                # No real intro content under the title (e.g. the
                # document jumps straight from its title into "Abstract"
                # or "Executive Summary") — skip the empty placeholder
                # slide entirely rather than showing "(No additional
                # detail provided)" right after the title slide.
                continue
            slide_title = "Overview" if (idx == 0 and heading == doc_title and len(sections) > 1) else heading
            for chunk in self._chunk_body(body, recipe.max_bullets_per_slide):
                slides.append(Slide(
                    order=order,
                    title=slide_title,
                    content_blocks=[
                        ContentBlock(type=BlockType.BULLET, text=b) for b in chunk
                    ],
                ))
                order += 1
        closing = self._closing_slide(order, recipe, slides)
        if closing is not None:
            slides.append(closing)
        return slides

    def _known_shape_fallback(self, text: str, recipe: Recipe) -> list[Slide]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text]

        word_count = len(text.split())
        title = self._guess_title(paragraphs[0])

        if word_count < THIN_CONTENT_WORD_THRESHOLD:
            return self._minimal_slides_for_thin_content(title, text, recipe)

        slides = [self._title_slide(title)]
        order = 2
        for para in paragraphs:
            for chunk in self._chunk_body(para, recipe.max_bullets_per_slide):
                slides.append(Slide(
                    order=order,
                    title=f"Key Point {order - 1}",
                    content_blocks=[
                        ContentBlock(type=BlockType.BULLET, text=b) for b in chunk
                    ],
                ))
                order += 1

        closing = self._closing_slide(order, recipe, slides)
        if closing is not None:
            slides.append(closing)
        return slides

    def _minimal_slides_for_thin_content(self, title: str, full_text: str, recipe: Recipe) -> list[Slide]:
        slides = [self._title_slide(title)]
        chunks = self._chunk_body(full_text, recipe.max_bullets_per_slide)
        for i, chunk in enumerate(chunks):
            slides.append(Slide(
                order=2 + i,
                title="Overview" if len(chunks) == 1 else f"Overview ({i + 1}/{len(chunks)})",
                content_blocks=[ContentBlock(type=BlockType.BULLET, text=b) for b in chunk],
            ))
        return slides

    def _chunk_body(self, body: str, max_bullets_per_slide: int) -> list[list[str]]:
        """Split a body of text into bullet points, then group into
        slide-sized chunks of at most max_bullets_per_slide (recipe-
        controlled density — Phase 3.5 Step 2).

        Splits on explicit bullet markers first (each '\\n'-separated
        line from _rejoin_lines is already one logical item if the
        source used bullet points); falls back to sentence-boundary
        splitting only for plain prose with no bullet structure."""
        if not body.strip():
            return [["(No additional detail provided)"]]

        lines = [l for l in body.split("\n") if l.strip()]
        has_bullet_structure = any(_BULLET_MARKER.match(l) for l in lines)

        bullets = []
        if has_bullet_structure:
            for line in lines:
                cleaned = _BULLET_MARKER.sub("", line).strip()
                if cleaned:
                    bullets.append(_smart_truncate(cleaned, BULLET_SAFETY_CEILING))
        else:
            raw_sentences = re.split(r"(?<=[.!?])\s+", body.strip())
            for s in raw_sentences:
                s = s.strip()
                if s:
                    bullets.append(_smart_truncate(s, BULLET_SAFETY_CEILING))

        if not bullets:
            bullets = [_smart_truncate(body, BULLET_SAFETY_CEILING)]

        return [
            bullets[i:i + max_bullets_per_slide]
            for i in range(0, len(bullets), max_bullets_per_slide)
        ] or [["(No additional detail provided)"]]

    def _guess_title(self, first_paragraph: str) -> str:
        first_sentence = re.split(r"(?<=[.!?])\s+", first_paragraph.strip())[0]
        return _smart_truncate(_strip_markdown_decoration(first_sentence), MAX_TITLE_LENGTH) or "Presentation"

    def _title_slide(self, title: str) -> Slide:
        return Slide(order=1, title=title, content_blocks=[])

    def _closing_slide(self, order: int, recipe: Recipe, existing_slides: list[Slide] | None = None) -> Slide | None:
        # Closing slide purpose comes from the recipe (Phase 3.5 Step 2)
        # — e.g. "Contact Information" for resumes, "Discussion" for
        # academic papers. But several real documents already have a
        # section with that exact title somewhere in the deck (a
        # paper's own "Discussion" section, a report's own
        # "Recommendations" section) — appending another slide with an
        # identical title looks like a duplication bug, not a feature.
        # Check anywhere in the deck, not just the last slide, since
        # the matching section isn't always the final one (e.g. an
        # academic paper's "Discussion" section followed by its own
        # separate "Conclusion" section).
        if existing_slides:
            existing_titles = {s.title.strip().lower() for s in existing_slides}
            if recipe.closing_slide_title.strip().lower() in existing_titles:
                return None
        return Slide(
            order=order,
            title=recipe.closing_slide_title,
            content_blocks=[ContentBlock(type=BlockType.NOTE, text="Thank you")],
        )
