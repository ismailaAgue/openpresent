import os
import pytest
from backend.models.recipe import StructureSource
from backend.engines.ai_generate import generate_presentation_from_topic, AIGenerationUnavailableError
from backend.adapters import registry


# -- Engine: with no AI adapter configured, generation now fails clearly
# (ADR-072 removed the deterministic-template fallback) ------------------

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


def test_engine_raises_when_no_ai_configured(monkeypatch):
    """ADR-072 — this used to fall back to a fully generic,
    topic-blind deterministic template (StructureSource.DETERMINISTIC_TOPIC)
    and silently succeed. That template, and the fallback path that
    produced it, are gone entirely: no AI provider configured now
    raises a clear, specific exception instead of a lesser deck."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "null")

    with pytest.raises(AIGenerationUnavailableError, match="No AI provider is configured"):
        generate_presentation_from_topic(topic="The Water Cycle", slide_count=5, export_format="pptx")


def test_engine_rejects_empty_topic():
    with pytest.raises(ValueError):
        generate_presentation_from_topic(topic="   ")


def test_engine_clamps_slide_count_is_caller_responsibility_but_survives_extremes(monkeypatch):
    # Engine itself doesn't clamp (the API layer does) — verify it still
    # produces a valid deck rather than crashing on an unusual count.
    # Uses FakeFullPipelineAdapter (defined below) rather than
    # OPENPRESENT_AI_ADAPTER=null — ADR-072 means "null" now raises
    # instead of producing output, so a real (fake) AI pipeline is
    # needed here to actually exercise slide-count survival.
    fake = FakeFullPipelineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
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


def test_engine_passes_requested_language_to_the_closing_slide_fix(monkeypatch):
    """ADR-060 — validate_and_fix() needs the request's language to
    localize the closing slide it may add; this confirms the engine
    actually passes it through end-to-end, not just that the function
    itself works in isolation (covered separately in
    test_quality_validator.py). Uses a dedicated fake (not
    FakeFullPipelineAdapter, whose last slide is deliberately titled
    "Thank You" already — an English closing-slide hint that would
    skip the auto-add path entirely and make this test pass for the
    wrong reason)."""
    class FakeNoClosingSlide:
        def is_available(self):
            return True

        def generate_strategy(self, request, research=None):
            from backend.ports.ai_pipeline import PresentationStrategy
            return PresentationStrategy(narrative_style="Classic Narrative", title_angle="Angle",
                                         key_themes=["t1"], tone_notes="")

        def generate_outline_structure(self, request, strategy):
            from backend.ports.ai_pipeline import SlideOutlineItem
            return [SlideOutlineItem(title=f"Slide {i+1}", purpose="purpose")
                    for i in range(request.slide_count)]

        def generate_slide_content(self, request, strategy, structure):
            from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
            slides = [
                Slide(order=i + 1, title=item.title, content_blocks=[
                    ContentBlock(type=BlockType.BULLET, text="a point"),
                ])
                for i, item in enumerate(structure)
            ]
            return Outline(structure_source=StructureSource.AI_GENERATED, slides=slides)

        def plan_layout(self, outline, request):
            for slide in outline.slides:
                slide.layout_type = "bullet_list"
            return outline

        def review_and_revise(self, outline, quality_report, request):
            return outline  # not expected to be called on a clean fixture

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: FakeNoClosingSlide())
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    recipe, _, _ = generate_presentation_from_topic(
        topic="Le Growth Marketing", slide_count=3, export_format="pptx", language="fr",
    )
    assert recipe.outline.slides[-1].title == "Merci"


def test_engine_raises_when_ai_pipeline_fails_every_attempt(monkeypatch):
    """ADR-072 — a failure mid-pipeline (even after ADR-070's retries
    are exhausted) used to drop the whole AI attempt back to the
    deterministic template and silently succeed with a generic deck.
    Now it raises instead — a real, actionable failure, not a lesser
    deck the caller doesn't know is lesser."""
    import backend.engines.ai_generate as engine_module
    monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)  # ADR-070 — don't
    # actually wait through 3 real retry attempts just to prove the
    # eventual failure still surfaces; the retry mechanics themselves
    # are covered directly by test_call_stage_with_retry_gives_up_after_exhausting_attempts.

    class AlwaysFails:
        def is_available(self):
            return True

        def generate_strategy(self, request, research=None):
            raise RuntimeError("simulated provider outage")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: AlwaysFails())
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    with pytest.raises(AIGenerationUnavailableError, match="AI generation failed after retries"):
        generate_presentation_from_topic(topic="Something", slide_count=4, export_format="pptx")


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


def test_on_stage_reports_only_the_first_bookend_before_raising_with_no_ai(monkeypatch):
    """ADR-072 — with no AI configured, generation now raises instead
    of falling back. The "understanding_request" bookend stage (set
    unconditionally before _run_ai_pipeline is even called) still
    reports — but the 3 mid-pipeline AI-only stages, and the LATER
    bookend stages (selecting_visuals, applying_design, which only run
    after a real outline exists) never fire, since the exception
    propagates out of generate_presentation_from_topic before reaching
    them. Before this, the later bookends still fired because a
    deterministic outline always existed to build a deck from — now
    there's nothing to build, so the function exits via exception
    partway through, not via a completed (if generic) deck."""
    monkeypatch.setenv("OPENPRESENT_AI_ADAPTER", "null")
    registry._ai_adapter_instance = None

    reported = []
    with pytest.raises(AIGenerationUnavailableError):
        generate_presentation_from_topic(
            topic="Volcanoes", slide_count=4, export_format="pptx",
            on_stage=reported.append,
        )

    assert reported == ["understanding_request"]


def test_on_stage_callback_raising_never_breaks_generation(monkeypatch):
    """A broken progress-reporting callback must never take down an
    otherwise-successful generation. Uses FakeFullPipelineAdapter, not
    OPENPRESENT_AI_ADAPTER=null (ADR-072 made "null" raise before ever
    reaching the callback meaningfully, which would test the wrong
    thing) — this needs a generation that actually SUCCEEDS despite the
    broken callback, to prove the callback's own failure is what's
    being tolerated, not AI unavailability."""
    fake = FakeFullPipelineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

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


# -- ADR-070: bounded retry around each AI stage call --------------------


def test_call_stage_with_retry_succeeds_immediately_without_retrying(monkeypatch):
    import backend.engines.ai_generate as engine_module
    sleeps = []
    monkeypatch.setattr(engine_module.time, "sleep", lambda s: sleeps.append(s))

    calls = []
    def fn(x):
        calls.append(x)
        return x * 2

    result = engine_module._call_stage_with_retry(fn, 5, stage_name="test_stage")
    assert result == 10
    assert calls == [5]  # called exactly once — no retry needed
    assert sleeps == []  # never slept — nothing failed


def test_call_stage_with_retry_recovers_from_one_transient_failure(monkeypatch):
    """A stage that fails once (a momentary rate limit, say) then
    succeeds on retry must return the SUCCESSFUL result, not give up
    after the first failure the way every AI call did before ADR-070."""
    import backend.engines.ai_generate as engine_module
    monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)  # don't actually wait in tests

    attempts = []
    def flaky():
        attempts.append(1)
        if len(attempts) < 2:
            raise ConnectionError("transient network blip")
        return "success"

    result = engine_module._call_stage_with_retry(flaky, stage_name="test_stage")
    assert result == "success"
    assert len(attempts) == 2  # failed once, succeeded on the retry


def test_call_stage_with_retry_gives_up_after_exhausting_attempts(monkeypatch):
    import backend.engines.ai_generate as engine_module
    monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)

    attempts = []
    def always_fails():
        attempts.append(1)
        raise RuntimeError("provider is fully down")

    with pytest.raises(RuntimeError, match="provider is fully down"):
        engine_module._call_stage_with_retry(always_fails, stage_name="test_stage")
    assert len(attempts) == engine_module.STAGE_RETRY_ATTEMPTS  # exhausted, not more, not fewer


def test_engine_recovers_when_one_stage_fails_once_then_succeeds(monkeypatch):
    """End-to-end version of the retry fix: before ADR-070, ANY single
    failure at ANY of the 4 sequential AI calls discarded the whole
    AI-generated deck and fell back to build_deterministic_outline's
    fully generic template — even if 3 of the 4 calls had already
    succeeded. This is the actual reported symptom (a real deck's
    closing slide kept coming back as the generic "Thank You" /
    "Questions?" fallback) traced to its root cause: zero retries
    anywhere in the AI adapter layer. This fixture's generate_strategy
    fails exactly once, then succeeds — the engine must still produce
    the real AI-generated deck, not the deterministic fallback."""
    import backend.engines.ai_generate as engine_module
    monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)

    class FlakyThenFineAdapter(FakeFullPipelineAdapter):
        def __init__(self):
            super().__init__()
            self._strategy_attempts = 0

        def generate_strategy(self, request, research=None):
            self._strategy_attempts += 1
            if self._strategy_attempts == 1:
                raise TimeoutError("provider timed out")
            return super().generate_strategy(request, research)

    fake = FlakyThenFineAdapter()
    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: fake)
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    recipe, output_bytes, quality = generate_presentation_from_topic(
        topic="Ebola", slide_count=4, export_format="pptx",
    )
    # The REAL AI-generated deck was used, not the generic fallback —
    # this is the whole point of the fix.
    assert recipe.outline.structure_source == StructureSource.AI_GENERATED
    assert fake._strategy_attempts == 2  # failed once, succeeded on retry
    assert len(output_bytes) > 0


def test_engine_raises_when_a_stage_fails_every_attempt(monkeypatch):
    """ADR-072 — the all-or-nothing boundary itself is unchanged in
    spirit: a GENUINELY down provider (fails all STAGE_RETRY_ATTEMPTS
    attempts, not just a transient blip) must still fail the whole
    generation rather than silently return a partial or fabricated
    result. What changed (ADR-072) is WHAT happens at that boundary —
    it used to land on the deterministic template and succeed
    silently; it now raises instead. Retries make transient failures
    resilient; they don't (and shouldn't) mask a hard, persistent
    failure as if it were a success."""
    import backend.engines.ai_generate as engine_module
    monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)

    class AlwaysFailsAdapter:
        def is_available(self):
            return True

        def generate_strategy(self, request, research=None):
            raise RuntimeError("provider is fully down")

    monkeypatch.setattr(registry, "get_ai_pipeline_adapter", lambda: AlwaysFailsAdapter())
    monkeypatch.setattr(registry, "get_research_adapter", lambda: registry.NullResearchAdapter())

    with pytest.raises(AIGenerationUnavailableError):
        generate_presentation_from_topic(topic="Ebola", slide_count=4, export_format="pptx")
