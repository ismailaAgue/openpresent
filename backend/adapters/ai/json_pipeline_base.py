"""
_JSONPipelineMixin — ADR-028, substantially revised ADR-030.

Shared prompt-building / response-parsing logic for any AIPipelinePort
adapter that talks to a model over a "send text prompt, get text back"
HTTP API (Gemini, local Ollama-compatible servers, Groq, OpenRouter,
HuggingFace — Section 6 of the spec: "changing inference backends
should not require application rewrites"). Each concrete adapter only
implements `_call_model()`; every prompt, every parse, every stage
lives here exactly once, shared by every provider.

ADR-030: five real stages (see backend/ports/ai_pipeline.py for why),
each with its own prompt builder and its own strict parser. Every
parser either returns a fully-validated structure or raises — no
partial/best-effort path leaks malformed model output further into
the system (spec Section 4, "Structured AI Contracts").
"""

import json
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.ports.ai_pipeline import (
    GenerationRequest, QualityReport, ResearchBrief, PresentationStrategy, SlideOutlineItem,
    SlideRegenerationContext,
)
from backend.pipeline.variety import NARRATIVE_STYLES, suggest_style

MAX_BULLETS_PER_SLIDE = 6
MAX_BULLET_LENGTH = 160
MAX_NOTE_LENGTH = 700
MAX_TITLE_LENGTH = 90
VALID_LAYOUT_TYPES = {"bullet_list", "statistics", "comparison", "process"}

# Output-token budget, scaled by slide count — ADR-030 fix for a real
# production bug: none of the provider adapters set an explicit output
# token limit, so every provider's (often modest) DEFAULT limit was in
# effect. That was invisible for small decks (a 3-slide response fits
# under almost any default) and silently truncated the JSON response —
# causing a json.loads() failure and a full fallback to the
# deterministic template — for anything larger. This is the same
# failure *shape* as the layout off-by-one bug (a hard assumption that
# happened to hold for small inputs and broke for larger ones): the
# fix here is the same philosophy, make the actual constraint explicit
# and generous rather than silently inherited from whatever a provider
# defaults to. Content generation (Stage 3, all slides' bullets+notes
# in one JSON response) is the largest payload and drives the budget;
# other stages request the same generous ceiling since asking for less
# saves little and risks the same class of bug reappearing if a prompt
# grows later.
_TOKENS_PER_SLIDE = 350
_TOKEN_BUDGET_FLOOR = 3072
_TOKEN_BUDGET_CEILING = 16000


def _token_budget(slide_count: int) -> int:
    return min(_TOKEN_BUDGET_CEILING, max(_TOKEN_BUDGET_FLOOR, slide_count * _TOKENS_PER_SLIDE + 1500))


# ADR-030 fix #2 (same root cause as the token budget above, different
# symptom): a bigger token budget means the model needs more wall-clock
# time to actually generate that many tokens — a fixed 45s read
# timeout, tuned for a small strategy/outline response, was too short
# for a full content-generation call on a 10+ slide deck. Scaled the
# same way, using the same slide_count input, so the two stay
# proportional to each other by construction rather than by
# coincidence (that's what broke last time: max_tokens scaled, timeout
# didn't, and the two silently drifted out of proportion).
_SECONDS_PER_SLIDE = 6
_READ_TIMEOUT_FLOOR = 45
_READ_TIMEOUT_CEILING = 180


def _read_timeout(slide_count: int) -> float:
    return min(_READ_TIMEOUT_CEILING, max(_READ_TIMEOUT_FLOOR, slide_count * _SECONDS_PER_SLIDE + 30))


class _JSONPipelineMixin:
    """Mixed into adapters that implement AIPipelinePort. Requires the
    concrete class to provide `_call_model(self, prompt: str, max_tokens: int) -> str`
    (raise on any failure — never return a sentinel)."""

    # -- Stage 1: Planner + Strategy -------------------------------------

    def generate_strategy(self, request: GenerationRequest,
                           research: ResearchBrief | None = None) -> PresentationStrategy:
        prompt = self._build_strategy_prompt(request, research)
        raw = self._call_model(prompt, max_tokens=_TOKEN_BUDGET_FLOOR, timeout=_READ_TIMEOUT_FLOOR)
        return self._parse_strategy_json(raw)

    def _build_strategy_prompt(self, request: GenerationRequest,
                                research: ResearchBrief | None) -> str:
        style_menu = "\n".join(f"- {s['name']}: {s['description']}" for s in NARRATIVE_STYLES)
        suggested = suggest_style()
        research_block = ""
        if research and research.facts:
            research_block = (
                "\nGrounding facts gathered about this topic (use what's relevant, "
                "ignore what isn't):\n- " + "\n- ".join(research.facts[:8]) + "\n"
            )
        brand_block = ""
        # ADR-045 — Brand Memory. Free text the model reads and weighs
        # alongside everything else here, not a hard constraint it must
        # satisfy exactly (a "must use these exact colors" instruction
        # would be a Layout-stage/theme concern, not a Strategy-stage
        # one — see ports/brand.py's module docstring for the full
        # scope line on why color mapping isn't wired any deeper than
        # this yet). An empty/unset brand profile produces this exact
        # empty string, so a workspace with no brand info gets the
        # identical prompt this always produced.
        if request.brand and not request.brand.is_empty():
            b = request.brand
            brand_lines = []
            if b.name:
                brand_lines.append(f"Brand/organization: {b.name}")
            if b.tone:
                brand_lines.append(f"Brand tone: {b.tone}")
            if b.audience:
                brand_lines.append(f"Brand's usual audience: {b.audience}")
            if b.visual_style:
                brand_lines.append(f"Visual style direction: {b.visual_style}")
            if b.colors:
                brand_lines.append(f"Brand colors (context only, not a hard layout constraint): {b.colors}")
            brand_block = (
                "\nThis deck is for a workspace with an established brand identity — "
                "let it inform tone_notes and the overall narrative feel, without "
                "overriding what actually fits this specific topic:\n"
                + "\n".join(f"- {line}" for line in brand_lines) + "\n"
            )
        return (
            "You are the strategist for a presentation-generation pipeline, planning "
            f"a {request.slide_count}-slide deck on: \"{request.topic}\".\n"
            f"Audience: {request.audience_type}. Language: {request.language}. "
            f"Tone: {request.tone}.\n" + research_block + brand_block +
            "\nChoose the narrative style that best fits this specific topic and "
            f"audience from this list:\n{style_menu}\n\n"
            f"(A randomly-suggested starting candidate is \"{suggested['name']}\" — use it "
            "only if it's genuinely a good fit; pick a different one if another style "
            "serves this topic better. Variety across different topics matters — don't "
            "default to the same style out of habit.)\n\n"
            "Also determine: a specific, compelling angle for the title slide (not just "
            "the topic restated), and 2-4 key themes the deck should keep returning to "
            "for narrative consistency.\n\n"
            "Respond with ONLY valid JSON, no markdown fences, no commentary:\n"
            '{"narrative_style": "string (must be one of the style names above)", '
            '"title_angle": "string", "key_themes": ["string", ...], "tone_notes": "string"}'
        )

    def _parse_strategy_json(self, raw: str) -> PresentationStrategy:
        data = json.loads(_strip_markdown_fences(raw))
        if not isinstance(data, dict) or not data.get("narrative_style"):
            raise ValueError("strategy response missing narrative_style")
        return PresentationStrategy(
            narrative_style=str(data["narrative_style"])[:60],
            title_angle=str(data.get("title_angle", ""))[:200],
            key_themes=[str(t)[:60] for t in (data.get("key_themes") or [])][:6],
            tone_notes=str(data.get("tone_notes", ""))[:300],
        )

    # -- Stage 2: Outline structure (titles + purpose only) --------------

    def generate_outline_structure(self, request: GenerationRequest,
                                    strategy: PresentationStrategy) -> list[SlideOutlineItem]:
        prompt = self._build_structure_prompt(request, strategy)
        raw = self._call_model(prompt, max_tokens=_token_budget(request.slide_count),
                                timeout=_read_timeout(request.slide_count))
        return self._parse_structure_json(raw, request)

    def _build_structure_prompt(self, request: GenerationRequest,
                                 strategy: PresentationStrategy) -> str:
        themes = ", ".join(strategy.key_themes) if strategy.key_themes else "(none specified)"
        n = request.slide_count
        return (
            f"Plan the slide-by-slide structure for a presentation on "
            f"\"{request.topic}\", using the \"{strategy.narrative_style}\" narrative "
            f"style. Title slide angle: \"{strategy.title_angle}\". "
            f"Key themes to weave through: {themes}.\n\n"
            f"Generate EXACTLY {n} slides TOTAL — not {n} plus a title slide, not {n} "
            f"plus a closing slide. All {n} slides, including the title slide and the "
            f"closing slide, count toward this total of {n}.\n"
            f"- Slide 1 (the first of these {n}) is the title slide.\n"
            f"- Slide {n} (the last of these {n}) must close the presentation "
            "(summary/conclusion/call-to-action).\n"
            f"- Slides 2 through {n - 1} cover the body content.\n\n"
            "For each slide, give a clear, specific title and a one-sentence purpose "
            "(what that slide needs to accomplish in the narrative — not its content "
            "yet, just its job).\n\n"
            "Respond with ONLY valid JSON:\n"
            '{"structure": [{"title": "string", "purpose": "string"}, ...]}\n'
            f"Count the items before responding: the \"structure\" array must have "
            f"exactly {n} items, no more and no fewer."
        )

    def _parse_structure_json(self, raw: str, request: GenerationRequest) -> list[SlideOutlineItem]:
        data = json.loads(_strip_markdown_fences(raw))
        if not isinstance(data, dict) or "structure" not in data:
            raise ValueError("structure response missing 'structure' key")
        items = data["structure"]
        if not isinstance(items, list) or not items:
            raise ValueError("structure response 'structure' is empty or not a list")

        # Deliberately tolerant of a SMALL count mismatch (same fix
        # philosophy as Stage 4's layout parser — see its comment for
        # the first instance of this bug class): models don't always
        # follow "exactly N" instructions precisely even with the
        # explicit wording above, and a real production case showed a
        # consistent off-by-one (N+1, always with an extra trailing
        # slide, never short) that used to discard the entire AI
        # attempt over one rounding error. Extra trailing items are
        # dropped; a slightly-short list is accepted as-is — every
        # later stage (content generation, layout planning) keys off
        # len(structure), the ACTUAL returned count, not
        # request.slide_count, so a slightly-different-than-requested
        # count stays internally consistent all the way through
        # rendering rather than causing a second mismatch downstream.
        # A genuinely wrong response (way too short, e.g. the model
        # produced 3 slides for a 15-slide request) still raises —
        # only small, plausibly-a-rounding-slip differences are
        # absorbed.
        n = request.slide_count
        tolerance = max(2, round(n * 0.15))
        if len(items) > n:
            items = items[:n]
        elif len(items) < n - tolerance:
            raise ValueError(f"expected {n} structure items, got {len(items)} "
                              f"(too short to safely accept)")

        result = []
        for item in items:
            if not isinstance(item, dict) or not item.get("title"):
                raise ValueError("structure item missing a title")
            result.append(SlideOutlineItem(
                title=str(item["title"]).strip()[:MAX_TITLE_LENGTH],
                purpose=str(item.get("purpose", "")).strip()[:200],
            ))
        return result

    # -- Stage 3: Slide content (bullets + speaker notes) -----------------

    def generate_slide_content(self, request: GenerationRequest, strategy: PresentationStrategy,
                                structure: list[SlideOutlineItem]) -> Outline:
        prompt = self._build_content_prompt(request, strategy, structure)
        raw = self._call_model(prompt, max_tokens=_token_budget(len(structure)),
                                timeout=_read_timeout(len(structure)))
        return self._parse_content_json(raw, structure, request.export_format)

    def _build_content_prompt(self, request: GenerationRequest, strategy: PresentationStrategy,
                               structure: list[SlideOutlineItem]) -> str:
        structure_block = "\n".join(
            f"{i+1}. \"{s.title}\" — purpose: {s.purpose}" for i, s in enumerate(structure)
        )
        # ADR-054 — content shape now depends on what this is actually
        # FOR, not always assumed to be a slide deck. Before this
        # branch existed, every export format (including document_docx,
        # infographic_svg, diagram_svg, poster_svg) received identical
        # terse bullet-fragment content, because this prompt always
        # asked for slide bullets regardless of the real target — the
        # literal reason a generated "document" read like a
        # reformatted deck instead of a real document.
        if request.export_format == "document_docx":
            content_instructions = (
                "For each section, write 1-3 short paragraphs of genuine connected "
                "prose (2-4 full sentences each) that thoroughly cover its stated "
                "purpose — real sentences with transitions, not sentence fragments, "
                "and NOT a bullet list. Every paragraph you write MUST end with "
                "terminal punctuation (a period, question mark, or exclamation "
                "point) — this is how the document renderer distinguishes prose "
                "paragraphs from a list, so a paragraph missing its final period "
                "will be misrendered as a list fragment. Also write 1-2 sentences "
                "of internal notes on this section's role in the document (not "
                "shown to the reader, this is not a repeat of the paragraphs)."
            )
            items_key_note = 'Put each paragraph as its own string in "bullets" — the key name is a holdover from the shared format, but here each entry is a full paragraph, not a fragment.'
        elif request.export_format in ("infographic_svg", "diagram_svg", "poster_svg"):
            content_instructions = (
                f"For each section, write 1-3 short, punchy, standalone claims (max "
                f"{MAX_BULLETS_PER_SLIDE}) that fulfill its stated purpose — each one "
                "a single complete idea a reader can grasp in a glance, not a "
                "sentence fragment and not a full paragraph. This content will "
                "appear in a compact visual layout with very limited space per "
                "section, so prioritize the single most important claim per line "
                "over covering everything. Also write 1-2 sentences of internal "
                "notes on this section's role (not shown to the reader)."
            )
            items_key_note = ""
        else:
            content_instructions = (
                "For each slide, write 3-5 concise bullet points (max "
                f"{MAX_BULLETS_PER_SLIDE}, fewer for the title slide) that fulfill its "
                "stated purpose — each bullet a single idea, not a paragraph. Also write "
                "1-2 sentences of speaker notes: what the presenter should actually say, "
                "not a repeat of the bullets."
            )
            items_key_note = ""
        return (
            f"Write the content for every section in this outline about "
            f"\"{request.topic}\" (audience: {request.audience_type}, "
            f"language: {request.language}, tone: {request.tone}):\n\n{structure_block}\n\n"
            f"{content_instructions} Use consistent terminology for key terms "
            "across every section (don't call the same thing two different names).\n\n"
            "Respond with ONLY valid JSON, same order as the outline above:\n"
            '{"slides": [{"title": "string", "bullets": ["string", ...], '
            '"speaker_notes": "string"}]}\n'
            f"The array must have exactly {len(structure)} items."
            + (f" {items_key_note}" if items_key_note else "")
        )

    def _parse_content_json(self, raw: str, structure: list[SlideOutlineItem],
                             export_format: str = "pptx") -> Outline:
        data = json.loads(_strip_markdown_fences(raw))
        if not isinstance(data, dict) or "slides" not in data:
            raise ValueError("content response missing 'slides' key")
        raw_slides = data["slides"]
        if not isinstance(raw_slides, list) or len(raw_slides) != len(structure):
            raise ValueError(f"expected {len(structure)} slides, got "
                              f"{len(raw_slides) if isinstance(raw_slides, list) else 'non-list'}")

        # ADR-054 — document_docx content is genuine multi-sentence
        # prose, not fragments, per _build_content_prompt's branch for
        # this format; MAX_BULLET_LENGTH (160 chars) is sized for a
        # slide-bullet fragment and would routinely cut a real
        # paragraph off mid-sentence, destroying the trailing
        # punctuation the document renderer's paragraph-vs-list
        # detection depends on (document_docx_adapter.py). A document
        # paragraph gets a much longer ceiling; every other format
        # keeps the original fragment-sized limit unchanged.
        max_len = 1200 if export_format == "document_docx" else MAX_BULLET_LENGTH

        slides = []
        for i, item in enumerate(raw_slides):
            if not isinstance(item, dict):
                raise ValueError(f"slide {i + 1} is not an object")
            # Title comes from the already-validated outline structure, not
            # re-parsed from this call — keeps Stage 2 and Stage 3 from
            # silently disagreeing about slide titles.
            title = structure[i].title
            bullets = item.get("bullets", []) or []
            if not isinstance(bullets, list):
                bullets = [str(bullets)]
            blocks = [
                ContentBlock(type=BlockType.BULLET, text=str(b).strip()[:max_len])
                for b in bullets[:MAX_BULLETS_PER_SLIDE] if str(b).strip()
            ]
            notes = str(item.get("speaker_notes", "")).strip()[:MAX_NOTE_LENGTH]
            if notes:
                blocks.append(ContentBlock(type=BlockType.NOTE, text=notes))
            slides.append(Slide(order=i + 1, title=title, content_blocks=blocks))

        return Outline(structure_source=StructureSource.AI_GENERATED, slides=slides,
                        document_type="ai_topic")

    # -- Stage 4: AI-driven layout planning (ADR-030) ---------------------

    def plan_layout(self, outline: Outline, request: GenerationRequest) -> Outline:
        prompt = self._build_layout_prompt(outline)
        raw = self._call_model(prompt, max_tokens=_token_budget(len(outline.slides)),
                                timeout=_read_timeout(len(outline.slides)))
        return self._parse_layout_json(raw, outline)

    def _build_layout_prompt(self, outline: Outline) -> str:
        slide_summaries = []
        for i, s in enumerate(outline.slides):
            bullets = [b.text for b in s.content_blocks if b.type == BlockType.BULLET]
            slide_summaries.append(f"{i+1}. \"{s.title}\" — bullets: {' | '.join(bullets)}")
        slides_block = "\n".join(slide_summaries)
        return (
            "You are choosing the visual layout for each slide of an already-written "
            f"presentation, based on its actual content:\n\n{slides_block}\n\n"
            "For EVERY slide listed above, INCLUDING the first (title) slide, choose "
            "exactly one layout_type from:\n"
            "- bullet_list: general content — always use this for the title slide, and "
            "the default for most other slides\n"
            "- statistics: the slide is centered on numbers/metrics/data points\n"
            "- comparison: the slide contrasts two or more things side by side\n"
            "- process: the slide describes sequential steps or a workflow\n\n"
            "Also suggest a short, concrete image search query (2-5 words) for slides "
            "where a photo would genuinely add value — this commonly includes the title "
            "slide. Skip it (use null) for slides that are purely about numbers, "
            "comparisons, or steps, where a generic stock photo doesn't help.\n\n"
            "Respond with ONLY valid JSON, exactly one entry per slide listed above "
            "(including the title slide), in the same order:\n"
            '{"layouts": [{"layout_type": "string", "image_query": "string or null"}]}\n'
            f"The array must have exactly {len(outline.slides)} items — one per slide."
        )

    def _parse_layout_json(self, raw: str, outline: Outline) -> Outline:
        data = json.loads(_strip_markdown_fences(raw))
        if not isinstance(data, dict) or "layouts" not in data:
            raise ValueError("layout response missing 'layouts' key")
        layouts = data["layouts"]
        if not isinstance(layouts, list) or not layouts:
            raise ValueError("layout response 'layouts' is empty or not a list")

        # Deliberately tolerant of a count that's slightly off from
        # len(outline.slides): models don't always follow "exactly N
        # items" instructions precisely (this exact mismatch — the
        # model including or excluding the title slide inconsistently
        # — was a real production bug caught via Sentry/log output and
        # is exactly what this leniency now absorbs). zip() truncates
        # to the shorter of the two lists; any slide left unmatched
        # simply keeps the Slide model's safe default
        # (layout_type="bullet_list", image_query=None) — never
        # broken, just less personalized. Unlike Stage 3 (content),
        # where a count mismatch means genuinely missing/misaligned
        # text and the whole attempt must be discarded, a partial
        # layout match here is always safe to apply as far as it goes.
        for slide, entry in zip(outline.slides, layouts):
            if not isinstance(entry, dict):
                continue
            layout_type = str(entry.get("layout_type", "bullet_list"))
            slide.layout_type = layout_type if layout_type in VALID_LAYOUT_TYPES else "bullet_list"
            image_query = entry.get("image_query")
            slide.image_query = str(image_query)[:100] if image_query else None
        return outline

    # -- Stage 5: Review + revision ---------------------------------------

    def review_and_revise(self, outline: Outline, report: QualityReport,
                           request: GenerationRequest) -> Outline:
        prompt = self._build_revision_prompt(outline, report, request)
        raw = self._call_model(prompt, max_tokens=_token_budget(len(outline.slides)),
                                timeout=_read_timeout(len(outline.slides)))
        return self._parse_revision_json(raw, outline)

    def _build_revision_prompt(self, outline: Outline, report: QualityReport,
                                request: GenerationRequest) -> str:
        current = {
            "slides": [
                {
                    "title": s.title,
                    "bullets": [b.text for b in s.content_blocks if b.type == BlockType.BULLET],
                    "speaker_notes": next(
                        (b.text for b in s.content_blocks if b.type == BlockType.NOTE), ""
                    ),
                }
                for s in outline.slides
            ]
        }
        return (
            "You are revising a presentation outline to fix specific quality issues. "
            f"Topic: \"{request.topic}\". Audience: {request.audience_type}. "
            f"Language: {request.language}.\n\n"
            "Current outline (JSON):\n" + json.dumps(current) + "\n\n"
            "Issues to fix:\n- " + "\n- ".join(report.issues) + "\n\n"
            "Fix ONLY these issues. Keep every slide's core topic, title, and general "
            "position in the narrative the same — only adjust bullets/notes as needed "
            "to resolve the listed issues. Do not add or remove slides — return "
            f"exactly {len(outline.slides)} slides, titles unchanged.\n\n"
            "Respond with ONLY valid JSON, the same shape as the input: "
            '{"slides": [{"title": "string", "bullets": ["string", ...], '
            '"speaker_notes": "string"}]}'
        )

    def _parse_revision_json(self, raw: str, original: Outline) -> Outline:
        data = json.loads(_strip_markdown_fences(raw))
        if not isinstance(data, dict) or "slides" not in data:
            raise ValueError("revision response missing 'slides' key")
        raw_slides = data["slides"]
        if not isinstance(raw_slides, list) or len(raw_slides) != len(original.slides):
            raise ValueError(f"expected {len(original.slides)} slides, got "
                              f"{len(raw_slides) if isinstance(raw_slides, list) else 'non-list'}")

        for slide, item in zip(original.slides, raw_slides):
            if not isinstance(item, dict):
                raise ValueError("revised slide is not an object")
            bullets = item.get("bullets", []) or []
            if not isinstance(bullets, list):
                bullets = [str(bullets)]
            blocks = [
                ContentBlock(type=BlockType.BULLET, text=str(b).strip()[:MAX_BULLET_LENGTH])
                for b in bullets[:MAX_BULLETS_PER_SLIDE] if str(b).strip()
            ]
            notes = str(item.get("speaker_notes", "")).strip()[:MAX_NOTE_LENGTH]
            if notes:
                blocks.append(ContentBlock(type=BlockType.NOTE, text=notes))
            slide.content_blocks = blocks  # layout_type/image_query untouched — Stage 4 already set them
        return original

    # -- Slide-level editing / partial regeneration (ADR-038) -------------

    def regenerate_slide(self, context: SlideRegenerationContext) -> tuple[str, list[str], str]:
        prompt = self._build_regenerate_slide_prompt(context)
        raw = self._call_model(prompt, max_tokens=_TOKEN_BUDGET_FLOOR, timeout=_READ_TIMEOUT_FLOOR)
        return self._parse_regenerate_slide_json(raw)

    def _build_regenerate_slide_prompt(self, context: SlideRegenerationContext) -> str:
        others = "; ".join(context.other_slide_titles) or "(no other slides)"
        current_bullets = "\n".join(f"- {b}" for b in context.current_bullets) or "(none)"
        instruction_block = ""
        if context.instructions and context.instructions.strip():
            instruction_block = (
                f"\nThe presenter specifically asked for this: \"{context.instructions.strip()}\"\n"
                "Prioritize honoring that request over anything else below."
            )
        return (
            f"You are rewriting ONE slide of an existing presentation "
            f"(context: {context.topic_or_source_summary[:500]}). "
            f"Audience: {context.audience_type}. Language: {context.language}.\n\n"
            f"Every OTHER slide's title, for context and to avoid duplicating "
            f"their content: {others}\n\n"
            f"Current title: \"{context.current_title}\"\n"
            f"Current bullets:\n{current_bullets}\n"
            f"Current speaker notes: {context.current_notes or '(none)'}\n"
            f"{instruction_block}\n\n"
            "Write a genuinely improved or different version of this ONE slide — "
            "not a trivial rewording of the same points. Keep it consistent in tone "
            "and narrative position with the other slides listed above; don't "
            "duplicate what another slide already covers. 3-5 concise bullets, "
            "1-2 sentences of speaker notes.\n\n"
            "Respond with ONLY valid JSON:\n"
            '{"title": "string", "bullets": ["string", ...], "speaker_notes": "string"}'
        )

    def _parse_regenerate_slide_json(self, raw: str) -> tuple[str, list[str], str]:
        data = json.loads(_strip_markdown_fences(raw))
        if not isinstance(data, dict) or not data.get("title"):
            raise ValueError("regenerate_slide response missing a title")
        bullets = data.get("bullets", []) or []
        if not isinstance(bullets, list):
            bullets = [str(bullets)]
        cleaned_bullets = [str(b).strip()[:MAX_BULLET_LENGTH] for b in bullets[:MAX_BULLETS_PER_SLIDE]
                            if str(b).strip()]
        if not cleaned_bullets:
            raise ValueError("regenerate_slide response has no usable bullets")
        title = str(data["title"]).strip()[:MAX_TITLE_LENGTH]
        notes = str(data.get("speaker_notes", "")).strip()[:MAX_NOTE_LENGTH]
        return title, cleaned_bullets, notes


class _TextEnhancementMixin:
    """Raising (non-degrading) implementations of the AIPort text
    capabilities — ADR-033. Shared by every adapter, analogous to
    _JSONPipelineMixin for the pipeline stages. Requires the concrete
    class to provide `_call_text(self, prompt: str) -> str` (plain
    text, not JSON mode; raise on any failure — never return a
    sentinel).

    Exists specifically so CompositeAIAdapter can cascade through
    multiple providers for these methods (propose_structure/rewrite/
    translate/summarize/suggest), the same way it already does for
    the AIPipelinePort stages. Before ADR-033, every adapter's public
    method caught its own exceptions and silently degraded internally
    — which meant "provider failed" and "provider succeeded but chose
    not to change anything" were indistinguishable to the composite,
    so cascading to a working provider was actually impossible even
    though the composite's code looked like it might try. Each
    adapter's PUBLIC method (propose_structure, rewrite, etc.) still
    wraps these _raising methods in a try/except that degrades safely
    — that behavior is unchanged for standalone (non-composite) use —
    but the composite now calls these _raising methods directly,
    catching between attempts itself, so a Gemini failure genuinely
    falls through to Groq/OpenRouter/HuggingFace instead of silently
    producing zero enhancement."""

    def _propose_structure_raising(self, outline: Outline, source_text: str,
                                    target_slide_count: int | None = None) -> Outline:
        prompt = build_structure_prompt(outline, source_text, target_slide_count)
        # ADR-034 fix: this is the one _TextEnhancementMixin method that
        # needs strict JSON output — the other four (rewrite/translate/
        # summarize/suggest) want plain text. Previously _call_text was
        # always called plain-text, relying purely on prompt wording
        # ("Respond ONLY with valid JSON") to get structured output —
        # which HuggingFace's router did not reliably follow, producing
        # a real production failure ("model response could not be
        # parsed into a valid outline") even though the call itself
        # succeeded. json_mode=True actually enforces the response
        # format at the API level wherever the provider supports it.
        raw = self._call_text(prompt, json_mode=True)
        result = parse_outline_response(raw, fallback=None)
        if result is None:
            raise ValueError("model response could not be parsed into a valid outline")
        return result

    def _rewrite_raising(self, text: str, instructions: str = "") -> str:
        prompt = f"Rewrite the following text. {instructions}\n\nText: {text}\n\nRewritten:"
        result = self._call_text(prompt).strip().strip('"').strip("'")
        if not result:
            raise ValueError("model returned an empty rewrite")
        return result

    def _translate_raising(self, text: str, target_language: str) -> str:
        prompt = f"Translate the following text to {target_language}. Return only the translation.\n\nText: {text}"
        result = self._call_text(prompt).strip()
        if not result:
            raise ValueError("model returned an empty translation")
        return result

    def _summarize_raising(self, text: str, max_length: int | None = None) -> str:
        length_hint = f" in under {max_length} characters" if max_length else ""
        prompt = f"Summarize the following text{length_hint}.\n\nText: {text}"
        result = self._call_text(prompt).strip()
        if not result:
            raise ValueError("model returned an empty summary")
        return result

    def _suggest_raising(self, context: str) -> list[str]:
        prompt = f"Given this context, suggest up to 3 short improvements, one per line:\n\n{context}"
        raw = self._call_text(prompt)
        result = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()][:3]
        if not result:
            raise ValueError("model returned no suggestions")
        return result

    def _answer_question_raising(self, context: str, question: str) -> str:
        # ADR-050. Explicitly instructed to stay grounded in the given
        # context rather than answering from general knowledge — the
        # point of this feature is "what does THIS document say,"
        # not a general chatbot riding on the document as a pretext.
        # Truncated to 4000 chars — more generous than build_structure_
        # prompt's 2000 (an outline-improvement prompt needs less
        # source material than answering an arbitrary question does),
        # but still bounded regardless of how large an uploaded
        # document is, same reasoning as that method, different number.
        prompt = (
            "Answer the question using ONLY the information in the document text below. "
            "If the document doesn't contain enough information to answer, say so plainly "
            "rather than guessing or using outside knowledge.\n\n"
            f"Document text:\n{context[:4000]}\n\nQuestion: {question}\n\nAnswer:"
        )
        result = self._call_text(prompt).strip()
        if not result:
            raise ValueError("model returned an empty answer")
        return result


def build_structure_prompt(outline: Outline, source_text: str,
                            target_slide_count: int | None = None) -> str:
    """Shared with LocalModelAdapter/GeminiAdapter's AIPort.propose_structure
    (the DOCUMENT-upload enhancement path — unrelated to the topic-first
    Stage 2 above, which is a differently-shaped, differently-named
    method to avoid confusing the two capabilities).

    target_slide_count (ADR-034): the document-upload flow's rule-based
    structure engine derives slide count organically from the source
    document's own section structure — there was previously no way to
    ask for a specific count, unlike the topic-first flow. This is a
    soft hint given to the AI enhancement pass, not a hard guarantee:
    if AI is unavailable or fails, the deck still renders at whatever
    count the rule-based baseline produced."""
    slide_titles = [s.title for s in outline.slides]
    count_hint = ""
    if target_slide_count:
        count_hint = (
            f" Aim for approximately {target_slide_count} slides total — "
            "consolidate related sections together if the source material "
            "would naturally produce more than that, or split out more detail "
            "if it would naturally produce fewer. This is a target, not a hard "
            "requirement if the source material genuinely doesn't fit."
        )
    return (
        "You are improving a presentation outline generated from a student's "
        "document. Current slide titles: " + ", ".join(slide_titles) + "." + count_hint + " "
        "Respond ONLY with valid JSON: a list of objects with 'title' and "
        "'bullets' (list of strings). Base it on this source text: " + source_text[:2000]
    )


def parse_outline_response(raw: str, fallback: Outline) -> Outline:
    """Shared with LocalModelAdapter/GeminiAdapter's AIPort.propose_structure."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback

    if not isinstance(data, list) or not data:
        return fallback

    slides = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "title" not in item:
            return fallback
        bullets = item.get("bullets", [])
        slides.append(Slide(
            order=i + 1,
            title=str(item["title"]),
            content_blocks=[ContentBlock(type=BlockType.BULLET, text=str(b)) for b in bullets],
        ))
    return Outline(structure_source=StructureSource.AI_ENHANCED, slides=slides)


def _strip_markdown_fences(text: str) -> str:
    """Models frequently wrap JSON in ```json ... ``` even when told
    not to — strip that instead of failing the whole generation on it."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
        t = t.strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    return t
