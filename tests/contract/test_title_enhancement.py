"""
Tests for Phase 3.5 Step 3 (ADR-021): AI title enhancement wiring.

Uses the same FakeHttpClient pattern as tests/contract/test_ai_port.py
to verify the engine's wiring without needing a real model server.
"""

import json
from backend.engines.generate import generate_presentation, _apply_title_enhancement, TITLE_REWRITE_INSTRUCTIONS
from backend.adapters.ai.local_model import LocalModelAdapter
from backend.adapters.ai.null_adapter import NullAdapter
from backend.models.recipe import Outline, Slide, StructureSource


class FakeHttpClient:
    def __init__(self, tags_status=200, generate_response=""):
        self.tags_status = tags_status
        self.generate_response = generate_response

    def get(self, url, timeout):
        return {"status_code": self.tags_status}

    def post(self, url, json, timeout):
        return {"status_code": 200, "json": {"response": self.generate_response}}


def make_outline(title="The Role of Government in Market Economies"):
    return Outline(structure_source=StructureSource.RULE_BASED, slides=[
        Slide(order=1, title=title, content_blocks=[]),
        Slide(order=2, title="Introduction", content_blocks=[]),
    ])


def test_title_enhanced_when_ai_available_and_returns_good_result():
    client = FakeHttpClient(generate_response="Why Markets Need Rules")
    ai = LocalModelAdapter(http_client=client)
    outline = make_outline()
    _apply_title_enhancement(outline, ai)
    assert outline.slides[0].title == "Why Markets Need Rules"


def test_title_unchanged_when_ai_unavailable():
    ai = NullAdapter()
    outline = make_outline()
    original_title = outline.slides[0].title
    _apply_title_enhancement(outline, ai)
    assert outline.slides[0].title == original_title


def test_title_unchanged_when_ai_returns_empty_result():
    client = FakeHttpClient(generate_response="")
    ai = LocalModelAdapter(http_client=client)
    outline = make_outline()
    original_title = outline.slides[0].title
    _apply_title_enhancement(outline, ai)
    assert outline.slides[0].title == original_title


def test_title_unchanged_when_ai_returns_absurdly_long_result():
    """Guard against a misbehaving model returning an entire paragraph
    instead of a short title."""
    client = FakeHttpClient(generate_response="A " * 60)  # way over the length cap
    ai = LocalModelAdapter(http_client=client)
    outline = make_outline()
    original_title = outline.slides[0].title
    _apply_title_enhancement(outline, ai)
    assert outline.slides[0].title == original_title


def test_only_title_slide_is_touched_not_section_headings():
    """Regression guard: section headings and recipe-driven closing
    slides must never be rewritten — only the title slide."""
    client = FakeHttpClient(generate_response="Some Rewritten Text")
    ai = LocalModelAdapter(http_client=client)
    outline = make_outline()
    original_section_title = outline.slides[1].title
    _apply_title_enhancement(outline, ai)
    assert outline.slides[1].title == original_section_title  # untouched


def test_full_pipeline_with_ai_enabled_still_produces_valid_pptx(monkeypatch):
    """End-to-end: with a fake AI adapter wired into the real registry,
    the full generate_presentation() pipeline still produces a valid
    file, and the title reflects the AI enhancement."""
    from backend.adapters import registry as reg

    fake_client = FakeHttpClient(generate_response="Why Markets Need Rules")
    fake_ai = LocalModelAdapter(http_client=fake_client)
    monkeypatch.setattr(reg, "get_ai_adapter", lambda: fake_ai)

    source = (
        "The Role of Government in Market Economies\n\n"
        "Introduction\n"
        "This essay discusses how governments intervene in markets to correct failures.\n"
    ).encode("utf-8")

    recipe, pptx_bytes = generate_presentation(
        file_bytes=source, filename="essay.txt", export_format="pptx"
    )

    assert recipe.outline.slides[0].title == "Why Markets Need Rules"
    assert pptx_bytes[:2] == b"PK"


def test_full_pipeline_with_ai_disabled_unaffected():
    """Confirms the default (NullAdapter) path is completely untouched
    by this change — same title as the rule-based engine alone produces."""
    source = (
        "The Role of Government in Market Economies\n\n"
        "Introduction\n"
        "This essay discusses how governments intervene in markets to correct failures.\n"
    ).encode("utf-8")

    recipe, pptx_bytes = generate_presentation(
        file_bytes=source, filename="essay.txt", export_format="pptx"
    )

    assert recipe.outline.slides[0].title == "The Role of Government in Market Economies"
    assert pptx_bytes[:2] == b"PK"


# -- Brand Memory closing the document-mode gap (ADR-045, continued) -------

class _RecordingAI:
    """A minimal AIPort-shaped fake that just records what instructions
    it was called with, rather than going through the full HTTP mock —
    the thing under test here is the instructions STRING built by
    _apply_title_enhancement, not the HTTP wire format LocalModelAdapter
    happens to use to send it."""
    def __init__(self, response="Rewritten Title"):
        self.response = response
        self.last_instructions = None

    def is_available(self):
        return True

    def rewrite(self, text, instructions=""):
        self.last_instructions = instructions
        return self.response


def test_brand_tone_and_visual_style_appended_to_rewrite_instructions():
    from backend.ports.brand import BrandProfile
    ai = _RecordingAI()
    outline = make_outline()
    brand = BrandProfile(workspace_id="ws1", owner_id="u1", tone="Playful", visual_style="Minimal")
    _apply_title_enhancement(outline, ai, brand)
    assert "Playful" in ai.last_instructions
    assert "Minimal" in ai.last_instructions


def test_no_brand_leaves_instructions_unchanged():
    ai = _RecordingAI()
    outline = make_outline()
    _apply_title_enhancement(outline, ai, brand=None)
    assert ai.last_instructions == TITLE_REWRITE_INSTRUCTIONS


def test_empty_brand_leaves_instructions_unchanged():
    from backend.ports.brand import BrandProfile
    ai = _RecordingAI()
    outline = make_outline()
    _apply_title_enhancement(outline, ai, brand=BrandProfile(workspace_id="ws1", owner_id="u1"))
    assert ai.last_instructions == TITLE_REWRITE_INSTRUCTIONS


def test_brand_with_only_name_and_colors_set_does_not_affect_instructions():
    """Only tone/visual_style are phrasing-relevant — name/colors/
    audience being set (but tone/visual_style NOT set) must leave the
    rewrite instructions untouched, per _apply_title_enhancement's own
    stated reasoning for which fields it reads."""
    from backend.ports.brand import BrandProfile
    ai = _RecordingAI()
    outline = make_outline()
    brand = BrandProfile(workspace_id="ws1", owner_id="u1", name="Acme", colors="Blue", audience="Investors")
    _apply_title_enhancement(outline, ai, brand)
    assert ai.last_instructions == TITLE_REWRITE_INSTRUCTIONS


# -- on_stage progress reporting (ADR-040) ------------------------------

SOURCE_TEXT = (
    "The Role of Government in Market Economies\n\n"
    "Introduction\n"
    "This essay discusses how governments intervene in markets to correct failures.\n"
).encode("utf-8")


def test_document_generation_with_brand_still_produces_valid_output(monkeypatch):
    """End-to-end proof through the real generate_presentation() call —
    not just the instruction-string unit tests above."""
    from backend.adapters import registry as reg
    from backend.ports.brand import BrandProfile

    fake_client = FakeHttpClient(generate_response="Why Markets Need Rules")
    fake_ai = LocalModelAdapter(http_client=fake_client)
    monkeypatch.setattr(reg, "get_ai_adapter", lambda: fake_ai)

    brand = BrandProfile(workspace_id="ws1", owner_id="u1", tone="Playful")
    recipe, pptx_bytes = generate_presentation(
        file_bytes=SOURCE_TEXT, filename="essay.txt", export_format="pptx", brand=brand,
    )
    assert pptx_bytes[:2] == b"PK"


def test_on_stage_reports_four_stages_when_ai_available(monkeypatch):
    from backend.adapters import registry as reg

    fake_client = FakeHttpClient(generate_response="Why Markets Need Rules")
    fake_ai = LocalModelAdapter(http_client=fake_client)
    monkeypatch.setattr(reg, "get_ai_adapter", lambda: fake_ai)

    reported = []
    generate_presentation(
        file_bytes=SOURCE_TEXT, filename="essay.txt", export_format="pptx",
        on_stage=reported.append,
    )

    assert reported == [
        "understanding_request", "building_outline", "generating_content", "applying_design",
    ]


def test_on_stage_skips_content_stage_when_ai_unavailable():
    # NullAdapter (default) — the AI-only "generating_content" stage never
    # fires because there's genuinely no AI-enhancement work happening,
    # not because reporting was forgotten for this path.
    reported = []
    generate_presentation(
        file_bytes=SOURCE_TEXT, filename="essay.txt", export_format="pptx",
        on_stage=reported.append,
    )

    assert reported == ["understanding_request", "building_outline", "applying_design"]


def test_on_stage_callback_raising_never_breaks_document_generation():
    def broken_callback(stage):
        raise RuntimeError("simulated broken progress sink")

    recipe, pptx_bytes = generate_presentation(
        file_bytes=SOURCE_TEXT, filename="essay.txt", export_format="pptx",
        on_stage=broken_callback,
    )
    assert pptx_bytes[:2] == b"PK"
