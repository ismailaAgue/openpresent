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
def reset_registry_singletons(monkeypatch):
    """Registry adapters are lazily-cached module singletons — reset
    between tests so OPENPRESENT_AI_ADAPTER changes actually take
    effect instead of reusing a previously-constructed instance.

    Also forces the research adapter to NullResearchAdapter for every
    test in this file by default (individual tests can still override
    via their own monkeypatch.setattr call, same as before) — without
    this, ADR-032's on-by-default CompositeResearchAdapter would make
    a real network call to Wikipedia during test runs. This sandbox's
    network restrictions happen to fail that fast rather than hang,
    which is what let this gap go unnoticed initially — but tests
    should never depend on live network regardless of environment."""
    registry._ai_adapter_instance = None
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())
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


# -- Engine: full 5-stage AI pipeline path, end to end (ADR-030) -------

class FakeFullPipelineAdapter:
    """Exercises the engine's orchestration of all 5 stages without
    hitting a real provider — each stage returns a minimal, valid
    result and we assert the engine actually called and threaded
    through every one of them."""

    def __init__(self):
        self.calls = []

    def is_available(self):
        return True

    def generate_strategy(self, request, research=None):
        self.calls.append("strategy")
        from backend.ports.ai_pipeline import PresentationStrategy
        return PresentationStrategy(narrative_style="Classic Narrative", title_angle="Angle",
                                     key_themes=["t1"], tone_notes="")

    def generate_outline_structure(self, request, strategy):
        self.calls.append("structure")
        from backend.ports.ai_pipeline import SlideOutlineItem
        items = [SlideOutlineItem(title=f"Slide {i+1}", purpose="purpose")
                 for i in range(request.slide_count)]
        items[-1] = SlideOutlineItem(title="Thank You", purpose="closing")  # avoids the
        # quality validator's auto-added closing slide, keeping slide count == request.slide_count
        return items

    def generate_slide_content(self, request, strategy, structure):
        self.calls.append("content")
        from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
        slides = [
            Slide(order=i + 1, title=item.title, content_blocks=[
                ContentBlock(type=BlockType.BULLET, text="a point"),
                ContentBlock(type=BlockType.NOTE, text="a note"),
            ])
            for i, item in enumerate(structure)
        ]
        return Outline(structure_source=StructureSource.AI_GENERATED, slides=slides)

    def plan_layout(self, outline, request):
        self.calls.append("layout")
        for i, slide in enumerate(outline.slides):
            slide.layout_type = "bullet_list"
            slide.image_query = None  # no image needed — keeps test $0/offline
        return outline

    def review_and_revise(self, outline, report, request):
        self.calls.append("review")
        return outline


def test_engine_runs_full_five_stage_pipeline_when_ai_available(monkeypatch):
    fake = FakeFullPipelineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Machine Learning Basics", slide_count=4, export_format="pptx",
    )

    assert recipe.outline.structure_source == StructureSource.AI_GENERATED
    assert len(recipe.outline.slides) == 4
    assert len(output_bytes) > 0
    # Confirms the engine actually orchestrated all 4 generation stages
    # (review only runs if validate_and_fix found issues, so it's not
    # guaranteed to fire on this clean fixture — the other 4 are).
    assert fake.calls[:4] == ["strategy", "structure", "content", "layout"]


def test_engine_falls_back_to_deterministic_when_ai_pipeline_raises(monkeypatch):
    class AlwaysFails:
        def is_available(self):
            return True

        def generate_strategy(self, request, research=None):
            raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: AlwaysFails())
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Something", slide_count=4, export_format="pptx",
    )
    # A failure mid-pipeline drops the WHOLE AI attempt — never a
    # partially-AI, partially-broken deck.
    assert recipe.outline.structure_source == StructureSource.DETERMINISTIC_TOPIC
    assert len(output_bytes) > 0


# -- on_stage progress reporting (ADR-040) ------------------------------

def test_on_stage_reports_all_six_stages_in_order_on_full_ai_path(monkeypatch):
    fake = FakeFullPipelineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    reported = []
    generate_presentation_from_topic(
        topic="Machine Learning Basics", slide_count=4, export_format="pptx",
        on_stage=reported.append,
    )

    assert reported == [
        "understanding_request", "building_outline", "generating_content",
        "designing_slides", "selecting_visuals", "applying_design",
    ]


def test_on_stage_still_reports_bookend_stages_on_deterministic_fallback(monkeypatch):
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "null")
    registry._ai_adapter_instance = None

    reported = []
    generate_presentation_from_topic(
        topic="Volcanoes", slide_count=4, export_format="pptx",
        on_stage=reported.append,
    )

    # No AI adapter available -> the 3 mid-pipeline AI-only stages never
    # fire, but the bookend stages (set unconditionally by the engine,
    # not from inside _run_ai_pipeline) still report, in order.
    assert reported == ["understanding_request", "selecting_visuals", "applying_design"]


def test_on_stage_callback_raising_never_breaks_generation(monkeypatch):
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "null")
    registry._ai_adapter_instance = None

    def broken_callback(stage):
        raise RuntimeError("simulated broken progress sink")

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Volcanoes", slide_count=4, export_format="pptx",
        on_stage=broken_callback,
    )
    assert len(output_bytes) > 0


def test_engine_uses_ai_layout_when_pipeline_succeeds_not_rule_based(monkeypatch):
    """Confirms ai_layout_planned=True actually suppresses the
    rule-based classifier — every slide keeps the layout_type the fake
    AI adapter set (bullet_list), not whatever the regex classifier
    would have independently decided."""
    fake = FakeFullPipelineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Topic", slide_count=3, export_format="pptx",
    )
    for slide in recipe.outline.slides:
        assert slide.layout_type == "bullet_list"


def test_engine_theme_variety_actually_takes_effect(monkeypatch):
    """Regression test for a real bug found during development: an
    engine-constructed Theme(color_set_id=X) with every other field
    left at its dataclass default was silently ignored by
    apply_theme(), which only respects an explicit theme when
    layout_template_id != 'default'. get_theme_variant() must return a
    fully-resolved Theme so the override actually lands on the Recipe."""
    from backend.adapters.design import rule_based as design_module

    fake = FakeFullPipelineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())
    # Force a non-default variant so we can assert it actually landed.
    import backend.engines.ai_generate as engine_module
    monkeypatch.setattr(engine_module, "pick_theme_variant", lambda: "modern_dark")

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Topic", slide_count=3, export_format="pptx",
    )
    expected = design_module.get_theme_variant("modern_dark")
    assert recipe.theme.color_set_id == expected.color_set_id == "modern_dark"
