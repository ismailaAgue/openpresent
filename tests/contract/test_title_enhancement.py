"""
Tests for Phase 3.5 Step 3 (ADR-021): AI title enhancement wiring.

Uses the same FakeHttpClient pattern as tests/contract/test_ai_port.py
to verify the engine's wiring without needing a real model server.
"""

import json
from backend.engines.generate import generate_presentation, _apply_title_enhancement
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
