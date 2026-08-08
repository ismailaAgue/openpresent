"""
_JSONPipelineMixin — ADR-028.

Shared prompt-building / response-parsing logic for any AIPipelinePort
adapter that talks to a model over a "send text prompt, get text back"
HTTP API (Gemini, local Ollama-compatible servers, and any future
OpenAI-compatible provider — Section 6 of the spec: "changing
inference backends should not require application rewrites"). Each
concrete adapter only has to implement `_call_model()`; parsing,
validation, and safe fallback behavior live here exactly once.

This is what "Structured AI Contracts" (spec Section 4) actually means
in code: the adapter never hands raw model text further into the
system. `_parse_outline_json` either returns a fully-validated Outline
or raises — there is no partial/best-effort path that could leave a
half-formed Recipe downstream.
"""

import json
from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
from backend.ports.ai_pipeline import GenerationRequest, QualityReport

MAX_BULLETS_PER_SLIDE = 6
MAX_BULLET_LENGTH = 160
MAX_NOTE_LENGTH = 700
MAX_TITLE_LENGTH = 90


class _JSONPipelineMixin:
    """Mixed into adapters that implement AIPipelinePort. Requires the
    concrete class to provide `_call_model(self, prompt: str) -> str`
    (raise on any failure — never return a sentinel)."""

    def generate_presentation_outline(self, request: GenerationRequest) -> Outline:
        prompt = self._build_outline_prompt(request)
        raw = self._call_model(prompt)
        return self._parse_outline_json(raw, request)

    def review_and_revise(self, outline: Outline, report: QualityReport,
                           request: GenerationRequest) -> Outline:
        prompt = self._build_revision_prompt(outline, report, request)
        raw = self._call_model(prompt)
        revised = self._parse_outline_json(raw, request, expected_slide_count=len(outline.slides))
        return revised

    # -- prompt construction ------------------------------------------

    def _build_outline_prompt(self, request: GenerationRequest) -> str:
        return (
            "You are an expert presentation designer. Create the content for a "
            f"{request.slide_count}-slide presentation on the topic: \"{request.topic}\".\n"
            f"Audience: {request.audience_type}. Language: {request.language}. "
            f"Tone: {request.tone}.\n\n"
            "Requirements:\n"
            "- Slide 1 is a title slide (a short, compelling title; 1 bullet is fine, "
            "used as a subtitle).\n"
            "- The last slide should close the presentation (summary, conclusion, or "
            "a clear call to action/next steps) — never end abruptly.\n"
            "- Every other slide needs a clear, specific title and 3-5 concise bullet "
            f"points (max {MAX_BULLETS_PER_SLIDE}), each a single idea, not a paragraph.\n"
            "- Vary the narrative structure across slides (don't repeat the same idea "
            "twice in different words).\n"
            "- Include one to two sentences of speaker notes per slide — what the "
            "presenter should actually say, not a repeat of the bullets.\n"
            "- Use consistent terminology for key terms throughout.\n\n"
            "Respond with ONLY valid JSON (no markdown fences, no commentary), matching "
            "exactly this shape:\n"
            '{"slides": [{"title": "string", "bullets": ["string", ...], '
            '"speaker_notes": "string"}]}\n'
            f"The \"slides\" array must have exactly {request.slide_count} items."
        )

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
            "Fix ONLY these issues. Keep every slide's core topic and general position "
            "in the narrative the same. Do not add or remove slides — return exactly "
            f"{len(outline.slides)} slides.\n\n"
            "Respond with ONLY valid JSON, the same shape as the input: "
            '{"slides": [{"title": "string", "bullets": ["string", ...], '
            '"speaker_notes": "string"}]}'
        )

    # -- response parsing -----------------------------------------------

    def _parse_outline_json(self, raw: str, request: GenerationRequest,
                             expected_slide_count: int | None = None) -> Outline:
        cleaned = _strip_markdown_fences(raw)
        data = json.loads(cleaned)  # let this raise — caller (engine) catches and falls back

        if not isinstance(data, dict) or "slides" not in data:
            raise ValueError("model response missing 'slides' key")
        raw_slides = data["slides"]
        if not isinstance(raw_slides, list) or not raw_slides:
            raise ValueError("model response 'slides' is empty or not a list")

        want = expected_slide_count or request.slide_count
        if len(raw_slides) != want:
            raise ValueError(f"expected {want} slides, model returned {len(raw_slides)}")

        slides = []
        for i, item in enumerate(raw_slides):
            if not isinstance(item, dict) or not item.get("title"):
                raise ValueError(f"slide {i + 1} missing a title")

            title = str(item["title"]).strip()[:MAX_TITLE_LENGTH]
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

            slides.append(Slide(order=i + 1, title=title, content_blocks=blocks))

        return Outline(structure_source=StructureSource.AI_GENERATED, slides=slides,
                        document_type="ai_topic")


def build_structure_prompt(outline: Outline, source_text: str) -> str:
    """Shared with LocalModelAdapter.propose_structure — extracted here
    (rather than duplicated, or reached into via an unbound-method call)
    so any AIPort adapter can reuse the exact same prompt without a
    cross-class dependency on LocalModelAdapter specifically."""
    slide_titles = [s.title for s in outline.slides]
    return (
        "You are improving a presentation outline generated from a student's "
        "document. Current slide titles: " + ", ".join(slide_titles) + ". "
        "Respond ONLY with valid JSON: a list of objects with 'title' and "
        "'bullets' (list of strings). Base it on this source text: " + source_text[:2000]
    )


def parse_outline_response(raw: str, fallback: Outline) -> Outline:
    """Shared with LocalModelAdapter.propose_structure — see
    build_structure_prompt() docstring for why this lives here."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return fallback  # malformed model output -> keep the rule-based baseline

    if not isinstance(data, list) or not data:
        return fallback

    slides = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or "title" not in item:
            return fallback  # any malformed entry -> discard the whole AI attempt, don't half-apply it
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
