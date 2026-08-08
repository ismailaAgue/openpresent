import os
import pytest
from backend.pipeline.deterministic_topic_outline import build_deterministic_outline
from backend.ports.ai_pipeline import GenerationRequest
from backend.models.recipe import StructureSource
from backend.engines.ai_generate import generate_presentation_from_topic
from backend.adapters import registry


def test_deterministic_outline_has_requested_slide_count():
    req = GenerationRequest(topic="Volcanoes", slide_count=6)
    outline = build_deterministic_outline(req)
    assert len(outline.slides) == 6
    assert outline.structure_source == StructureSource.DETERMINISTIC_TOPIC


def test_deterministic_outline_title_and_closing_slide():
    req = GenerationRequest(topic="Volcanoes", slide_count=5)
    outline = build_deterministic_outline(req)
    assert outline.slides[0].title == "Volcanoes"
    assert "thank" in outline.slides[-1].title.lower()


def test_deterministic_outline_never_below_three_slides():
    req = GenerationRequest(topic="X", slide_count=1)
    outline = build_deterministic_outline(req)
    assert len(outline.slides) >= 3


# -- Engine: with no AI adapter configured, falls back cleanly ---------

@pytest.fixture(autouse=True)
def reset_registry_singletons():
    """Registry adapters are lazily-cached module singletons — reset
    between tests so OPENPRESENT_AI_ADAPTER changes actually take
    effect instead of reusing a previously-constructed instance."""
    registry._ai_adapter_instance = None
    yield
    registry._ai_adapter_instance = None


def test_engine_falls_back_to_deterministic_when_no_ai_configured(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "null")

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="The Water Cycle", slide_count=5, export_format="pptx",
    )
    assert recipe.outline.structure_source == StructureSource.DETERMINISTIC_TOPIC
    assert len(output_bytes) > 0  # a real pptx byte stream was produced
    assert quality.score >= 0


def test_engine_rejects_empty_topic():
    with pytest.raises(ValueError):
        generate_presentation_from_topic(topic="   ")


def test_engine_clamps_slide_count_is_caller_responsibility_but_survives_extremes(monkeypatch):
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "null")
    # Engine itself doesn't clamp (the API layer does) — verify it still
    # produces a valid deck rather than crashing on an unusual count.
    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Something", slide_count=3, export_format="pptx",
    )
    assert len(recipe.outline.slides) >= 3
    assert len(output_bytes) > 0
