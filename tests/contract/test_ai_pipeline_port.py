import json
import pytest
from backend.adapters.ai.gemini_adapter import GeminiAdapter
from backend.adapters.ai.local_model import LocalModelAdapter
from backend.adapters.ai.groq_adapter import GroqAdapter
from backend.adapters.ai.composite_adapter import CompositeAIAdapter
from backend.ports.ai_pipeline import (
    GenerationRequest, PresentationStrategy, SlideOutlineItem, QualityReport,
    SlideRegenerationContext,
)
from backend.models.recipe import StructureSource


def make_request(slide_count=3):
    return GenerationRequest(topic="Photosynthesis", slide_count=slide_count,
                              audience_type="student_school", language="en")


def make_strategy():
    return PresentationStrategy(narrative_style="Classic Narrative", title_angle="An angle",
                                 key_themes=["theme1"], tone_notes="")


def make_structure(n=3):
    return [SlideOutlineItem(title=f"Slide {i+1}", purpose="purpose") for i in range(n)]


def strategy_json():
    return json.dumps({"narrative_style": "Classic Narrative", "title_angle": "An angle",
                        "key_themes": ["a", "b"], "tone_notes": "neutral"})


def structure_json(n=3):
    return json.dumps({"structure": [
        {"title": f"Slide {i+1}", "purpose": f"purpose {i+1}"} for i in range(n)
    ]})


def content_json(n=3):
    return json.dumps({"slides": [
        {"title": f"Slide {i+1}", "bullets": [f"point {i+1}a", f"point {i+1}b"],
         "speaker_notes": f"notes for slide {i+1}"}
        for i in range(n)
    ]})


def layout_json(n=3):
    return json.dumps({"layouts": [
        {"layout_type": "bullet_list", "image_query": "a query"} for _ in range(n)
    ]})


def gemini_with(text: str):
    def fake_post(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return GeminiAdapter(api_key="fake-key", http_post=fake_post)


# -- Stage 1: Strategy -----------------------------------------------------

def test_gemini_generates_strategy():
    adapter = gemini_with(strategy_json())
    strategy = adapter.generate_strategy(make_request(3))
    assert strategy.narrative_style == "Classic Narrative"
    assert strategy.key_themes == ["a", "b"]


def test_gemini_strategy_raises_on_missing_narrative_style():
    adapter = gemini_with(json.dumps({"title_angle": "x"}))
    with pytest.raises(ValueError):
        adapter.generate_strategy(make_request(3))


def test_gemini_strategy_accepts_research_brief_without_erroring():
    from backend.ports.ai_pipeline import ResearchBrief
    adapter = gemini_with(strategy_json())
    strategy = adapter.generate_strategy(make_request(3), ResearchBrief(facts=["fact one"]))
    assert strategy.narrative_style


# -- Brand Memory prompt injection (ADR-045) --------------------------------

def test_strategy_prompt_includes_brand_fields_when_present():
    from backend.ports.brand import BrandProfile
    adapter = gemini_with(strategy_json())
    brand = BrandProfile(workspace_id="ws1", owner_id="u1", name="Acme Corp",
                          tone="Playful but credible", audience="Enterprise investors",
                          visual_style="Minimal and clean", colors="Blue and purple")
    request = GenerationRequest(topic="Photosynthesis", slide_count=3, brand=brand)
    prompt = adapter._build_strategy_prompt(request, None)
    assert "Acme Corp" in prompt
    assert "Playful but credible" in prompt
    assert "Enterprise investors" in prompt
    assert "Minimal and clean" in prompt
    assert "Blue and purple" in prompt


def test_strategy_prompt_omits_brand_block_when_brand_is_none():
    adapter = gemini_with(strategy_json())
    request = make_request(3)  # brand defaults to None
    prompt = adapter._build_strategy_prompt(request, None)
    assert "brand identity" not in prompt.lower()


def test_strategy_prompt_omits_brand_block_when_brand_is_empty():
    """An all-blank BrandProfile (e.g. a workspace where the fields
    were set then cleared) must produce no brand block, exactly like
    no brand at all — is_empty() is exactly what makes this true.
    (Can't compare full prompts for equality since suggest_style()
    randomizes an unrelated part of the prompt on every call.)"""
    from backend.ports.brand import BrandProfile
    adapter = gemini_with(strategy_json())
    empty_brand = BrandProfile(workspace_id="ws1", owner_id="u1")
    with_none = GenerationRequest(topic="Photosynthesis", slide_count=3, brand=None)
    with_empty = GenerationRequest(topic="Photosynthesis", slide_count=3, brand=empty_brand)
    assert "brand identity" not in adapter._build_strategy_prompt(with_none, None).lower()
    assert "brand identity" not in adapter._build_strategy_prompt(with_empty, None).lower()


def test_strategy_prompt_only_includes_set_brand_fields():
    """A brand profile with only SOME fields set must not inject
    placeholder text for the unset ones."""
    from backend.ports.brand import BrandProfile
    adapter = gemini_with(strategy_json())
    brand = BrandProfile(workspace_id="ws1", owner_id="u1", tone="Playful")  # only tone set
    request = GenerationRequest(topic="Photosynthesis", slide_count=3, brand=brand)
    prompt = adapter._build_strategy_prompt(request, None)
    assert "Brand tone: Playful" in prompt
    assert "Brand colors" not in prompt
    assert "Visual style direction" not in prompt


def test_generate_strategy_end_to_end_with_brand_still_parses_normally():
    """The brand block only changes the PROMPT sent, not response
    parsing — confirms end to end that a brand-augmented call still
    produces a normal, valid PresentationStrategy."""
    from backend.ports.brand import BrandProfile
    adapter = gemini_with(strategy_json())
    brand = BrandProfile(workspace_id="ws1", owner_id="u1", tone="Playful")
    request = GenerationRequest(topic="Photosynthesis", slide_count=3, brand=brand)
    strategy = adapter.generate_strategy(request)
    assert strategy.narrative_style == "Classic Narrative"


# -- Stage 2: Outline structure ---------------------------------------------

def test_gemini_generates_outline_structure():
    adapter = gemini_with(structure_json(3))
    structure = adapter.generate_outline_structure(make_request(3), make_strategy())
    assert len(structure) == 3
    assert structure[0].title == "Slide 1"


def test_gemini_structure_truncates_one_extra_item_regression():
    """Regression test for the exact production bug (caught via log
    output): the model consistently returned N+1 structure items for
    an N-slide request (15->16, 10->11) — always one too MANY, never
    short — apparently treating 'the last slide must close the
    presentation' as an additional slide rather than one within the
    requested count. The old strict-equality parser discarded the
    whole AI attempt over this single extra item; it must now truncate
    to the requested count instead."""
    adapter = gemini_with(structure_json(11))  # model returns 11 for a 10-slide request
    structure = adapter.generate_outline_structure(make_request(10), make_strategy())
    assert len(structure) == 10  # truncated, not discarded
    assert structure[0].title == "Slide 1"
    assert structure[-1].title == "Slide 10"  # the extra 11th item was dropped


def test_gemini_structure_accepts_slightly_short_response():
    """The other direction of the same tolerance — a response a
    couple of slides short of the target (well within the ~15%
    tolerance) is accepted as-is rather than discarded; downstream
    stages key off the actual returned count, not the original
    request, so this stays internally consistent."""
    adapter = gemini_with(structure_json(8))  # model returns 8 for a 10-slide request
    structure = adapter.generate_outline_structure(make_request(10), make_strategy())
    assert len(structure) == 8


def test_gemini_structure_raises_when_response_is_far_too_short():
    """A genuinely broken/truncated response (way under the target,
    well outside tolerance) still raises — the tolerance absorbs
    small rounding slips, not a fundamentally incomplete response."""
    adapter = gemini_with(structure_json(2))  # model returns 2 for a 15-slide request
    with pytest.raises(ValueError):
        adapter.generate_outline_structure(make_request(15), make_strategy())


def test_gemini_structure_raises_on_empty_response():
    adapter = gemini_with(json.dumps({"structure": []}))
    with pytest.raises(ValueError):
        adapter.generate_outline_structure(make_request(10), make_strategy())


# -- Stage 3: Slide content ---------------------------------------------------

def test_gemini_generates_slide_content():
    adapter = gemini_with(content_json(3))
    outline = adapter.generate_slide_content(make_request(3), make_strategy(), make_structure(3))
    assert outline.structure_source == StructureSource.AI_GENERATED
    assert len(outline.slides) == 3
    # Title comes from the outline STRUCTURE (stage 2), not re-parsed from stage 3
    assert outline.slides[0].title == "Slide 1"


def test_gemini_content_raises_on_wrong_slide_count():
    adapter = gemini_with(content_json(2))
    with pytest.raises(ValueError):
        adapter.generate_slide_content(make_request(3), make_strategy(), make_structure(3))


def test_gemini_content_strips_markdown_fences():
    fenced = "```json\n" + content_json(3) + "\n```"
    adapter = gemini_with(fenced)
    outline = adapter.generate_slide_content(make_request(3), make_strategy(), make_structure(3))
    assert len(outline.slides) == 3


def test_gemini_content_trims_excess_bullets_and_length():
    long_text = "x" * 500
    raw = json.dumps({"slides": [
        {"title": "T", "bullets": [long_text] * 10, "speaker_notes": long_text}
    ]})
    adapter = gemini_with(raw)
    outline = adapter.generate_slide_content(make_request(1), make_strategy(), make_structure(1))
    blocks = outline.slides[0].content_blocks
    assert len(blocks) <= 7  # 6 bullets max + 1 note
    assert all(len(b.text) <= 700 for b in blocks)


def test_gemini_raises_on_blocked_response():
    def fake_post(url, body, timeout):
        return {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}
    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    with pytest.raises(RuntimeError):
        adapter.generate_strategy(make_request(3))


# -- Stage 4: AI-driven layout planning (ADR-030) ----------------------------

def test_gemini_plans_layout_including_title_slide():
    """ADR-030 fix: the prompt now asks for one entry PER SLIDE,
    including the title slide, and the AI is free to assign it an
    image_query directly — no more hardcoded 'title slide always uses
    its own title as the query' special case."""
    from backend.models.recipe import Outline, Slide
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Title Slide", content_blocks=[]),
        Slide(order=2, title="Body A", content_blocks=[]),
        Slide(order=3, title="Body B", content_blocks=[]),
    ])
    adapter = gemini_with(layout_json(3))
    result = adapter.plan_layout(outline, make_request(3))
    for slide in result.slides:
        assert slide.layout_type == "bullet_list"
        assert slide.image_query == "a query"


def test_gemini_plan_layout_tolerates_off_by_one_count_regression():
    """Regression test for a real production bug (caught via the
    Sentry/stdout logging fix): the model returned one MORE layout
    entry than slides remaining after the old 'skip the title slide'
    instruction, and the old strict-count parser discarded the WHOLE
    AI attempt over it — silently dropping every generation to the
    deterministic fallback across every configured provider. The
    parser must now apply however many entries it got, zipped in
    order, rather than raising on any count mismatch."""
    from backend.models.recipe import Outline, Slide
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Title Slide", content_blocks=[]),
        Slide(order=2, title="Body A", content_blocks=[]),
        Slide(order=3, title="Body B", content_blocks=[]),
    ])
    # One extra entry beyond what a stricter prompt might expect —
    # must not raise.
    over_count = json.dumps({"layouts": [
        {"layout_type": "bullet_list", "image_query": "q1"},
        {"layout_type": "statistics", "image_query": "q2"},
        {"layout_type": "comparison", "image_query": "q3"},
        {"layout_type": "process", "image_query": "q4"},  # extra — no matching slide
    ]})
    adapter = gemini_with(over_count)
    result = adapter.plan_layout(outline, make_request(3))  # must not raise
    assert result.slides[0].layout_type == "bullet_list"
    assert result.slides[1].layout_type == "statistics"
    assert result.slides[2].layout_type == "comparison"


def test_gemini_plan_layout_tolerates_fewer_entries_than_slides():
    """The other direction of the same tolerance: fewer entries than
    slides must not raise — unmatched trailing slides simply keep the
    Slide model's safe default (bullet_list, no image)."""
    from backend.models.recipe import Outline, Slide
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Title Slide", content_blocks=[]),
        Slide(order=2, title="Body A", content_blocks=[]),
        Slide(order=3, title="Body B", content_blocks=[]),
    ])
    under_count = json.dumps({"layouts": [{"layout_type": "statistics", "image_query": "q1"}]})
    adapter = gemini_with(under_count)
    result = adapter.plan_layout(outline, make_request(3))  # must not raise
    assert result.slides[0].layout_type == "statistics"
    assert result.slides[1].layout_type == "bullet_list"  # untouched, safe default
    assert result.slides[2].layout_type == "bullet_list"  # untouched, safe default


def test_gemini_plan_layout_raises_on_empty_layouts_list():
    from backend.models.recipe import Outline, Slide
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Title Slide", content_blocks=[]),
    ])
    adapter = gemini_with(json.dumps({"layouts": []}))
    with pytest.raises(ValueError):
        adapter.plan_layout(outline, make_request(1))


def test_gemini_plan_layout_falls_back_to_bullet_list_for_invalid_type():
    from backend.models.recipe import Outline, Slide
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="Title Slide", content_blocks=[]),
        Slide(order=2, title="Body A", content_blocks=[]),
    ])
    bad_layout = json.dumps({"layouts": [
        {"layout_type": "bullet_list", "image_query": None},
        {"layout_type": "not_a_real_type", "image_query": None},
    ]})
    adapter = gemini_with(bad_layout)
    result = adapter.plan_layout(outline, make_request(2))
    assert result.slides[1].layout_type == "bullet_list"
    assert result.slides[1].image_query is None


# -- Stage 5: Review + revision ------------------------------------------------

def test_gemini_reviews_and_revises():
    from backend.models.recipe import Outline, Slide, ContentBlock, BlockType
    outline = Outline(structure_source=StructureSource.AI_GENERATED, slides=[
        Slide(order=1, title="A", content_blocks=[ContentBlock(type=BlockType.BULLET, text="old")]),
    ])
    report = QualityReport(score=5.0, issues=["some issue"])
    revised_json = json.dumps({"slides": [{"title": "A", "bullets": ["new point"], "speaker_notes": "n"}]})
    adapter = gemini_with(revised_json)
    result = adapter.review_and_revise(outline, report, make_request(1))
    bullets = [b.text for b in result.slides[0].content_blocks if b.type.value == "bullet"]
    assert bullets == ["new point"]


# -- LocalModelAdapter also implements all 5 stages (ADR-028/031) -----------

class FakeHttpClient:
    def __init__(self, tags_status=200, generate_response=""):
        self.tags_status = tags_status
        self.generate_response = generate_response

    def get(self, url, timeout):
        return {"status_code": self.tags_status}

    def post(self, url, json, timeout):
        return {"status_code": 200, "json": {"response": self.generate_response}}


def test_local_model_generates_strategy_when_reachable():
    client = FakeHttpClient(generate_response=strategy_json())
    adapter = LocalModelAdapter(http_client=client)
    strategy = adapter.generate_strategy(make_request(3))
    assert strategy.narrative_style == "Classic Narrative"


def test_local_model_pipeline_raises_when_unreachable():
    client = FakeHttpClient(tags_status=500)
    adapter = LocalModelAdapter(http_client=client)
    with pytest.raises(Exception):
        adapter.generate_strategy(make_request(3))


# -- GroqAdapter (OpenAI-compatible provider) --------------------------------

def test_groq_generates_strategy():
    def fake_post(url, api_key, body, timeout):
        return {"choices": [{"message": {"content": strategy_json()}}]}
    adapter = GroqAdapter(api_key="fake-key", http_post=fake_post)
    strategy = adapter.generate_strategy(make_request(3))
    assert strategy.narrative_style == "Classic Narrative"


def test_groq_unavailable_without_key():
    assert GroqAdapter(api_key="").is_available() is False


# -- CompositeAIAdapter cascading (ADR-030) ----------------------------------

class AlwaysFailsAdapter:
    def is_available(self):
        return True

    def generate_strategy(self, request, research=None):
        raise RuntimeError("simulated provider failure")


def test_composite_cascades_to_next_provider_on_failure():
    failing = AlwaysFailsAdapter()
    working = gemini_with(strategy_json())
    composite = CompositeAIAdapter([failing, working])
    strategy = composite.generate_strategy(make_request(3))
    assert strategy.narrative_style == "Classic Narrative"


def test_composite_raises_when_every_provider_fails():
    composite = CompositeAIAdapter([AlwaysFailsAdapter(), AlwaysFailsAdapter()])
    with pytest.raises(Exception):
        composite.generate_strategy(make_request(3))


def test_composite_unavailable_when_no_child_available():
    class NeverAvailable:
        def is_available(self):
            return False
    composite = CompositeAIAdapter([NeverAvailable()])
    assert composite.is_available() is False


def test_composite_skips_unavailable_providers():
    class NeverAvailable:
        def is_available(self):
            return False

        def generate_strategy(self, *a, **k):
            raise AssertionError("should never be called — not available")

    working = gemini_with(strategy_json())
    composite = CompositeAIAdapter([NeverAvailable(), working])
    strategy = composite.generate_strategy(make_request(3))
    assert strategy.narrative_style == "Classic Narrative"


# -- AIPort cascading (ADR-033 regression) -------------------------------
# Production bug: CompositeAIAdapter.propose_structure() (and rewrite/
# translate/summarize/suggest) only ever tried the FIRST available
# provider — if it failed, the document-upload flow silently produced
# ZERO AI enhancement instead of falling through to Groq/OpenRouter/
# HuggingFace, even with all three fully configured and available.
# Caught live: "upload a document" decks looked purely rule-based
# despite /health showing every provider configured and available.

def make_gemini_that_fails_propose_structure():
    def fake_post(url, body, timeout):
        # A response shape that will fail JSON parsing inside
        # parse_outline_response — simulates a real provider failure
        # without needing to mock urllib errors.
        return {"candidates": [{"content": {"parts": [{"text": "not valid json"}]}}]}
    return GeminiAdapter(api_key="fake-key", http_post=fake_post)


def make_gemini_that_succeeds_propose_structure():
    def fake_post(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(
            [{"title": "Improved Title", "bullets": ["a", "b"]}]
        )}]}}]}
    return GeminiAdapter(api_key="fake-key", http_post=fake_post)


def make_outline_for_enhancement():
    from backend.models.recipe import Outline, Slide, StructureSource
    return Outline(structure_source=StructureSource.RULE_BASED, slides=[
        Slide(order=1, title="Original Title", content_blocks=[]),
    ])


def test_composite_propose_structure_cascades_to_working_provider():
    failing = make_gemini_that_fails_propose_structure()
    working = make_gemini_that_succeeds_propose_structure()
    composite = CompositeAIAdapter([failing, working])
    outline = make_outline_for_enhancement()
    result = composite.propose_structure(outline, "source text")
    assert result.slides[0].title == "Improved Title"  # NOT the original — cascaded successfully


def test_composite_propose_structure_degrades_only_after_every_provider_fails():
    failing1 = make_gemini_that_fails_propose_structure()
    failing2 = make_gemini_that_fails_propose_structure()
    composite = CompositeAIAdapter([failing1, failing2])
    outline = make_outline_for_enhancement()
    result = composite.propose_structure(outline, "source text")
    assert result is outline  # both failed — safe degrade, never raises


def test_composite_rewrite_cascades_to_working_provider():
    def fake_post_fail(url, body, timeout):
        return {"candidates": []}  # triggers "no candidates" -> raises

    def fake_post_succeed(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": "A much better sentence."}]}}]}

    failing = GeminiAdapter(api_key="fake-key", http_post=fake_post_fail)
    working = GeminiAdapter(api_key="fake-key", http_post=fake_post_succeed)
    composite = CompositeAIAdapter([failing, working])
    result = composite.rewrite("original text")
    assert result == "A much better sentence."


def test_composite_rewrite_degrades_to_original_when_all_fail():
    def fake_post_fail(url, body, timeout):
        return {"candidates": []}

    composite = CompositeAIAdapter([
        GeminiAdapter(api_key="fake-key", http_post=fake_post_fail),
        GeminiAdapter(api_key="fake-key", http_post=fake_post_fail),
    ])
    result = composite.rewrite("original text")
    assert result == "original text"


def test_composite_summarize_respects_max_length_on_full_degrade():
    def fake_post_fail(url, body, timeout):
        return {"candidates": []}

    composite = CompositeAIAdapter([GeminiAdapter(api_key="fake-key", http_post=fake_post_fail)])
    result = composite.summarize("a very long piece of text here", max_length=10)
    assert result == "a very lon"  # first 10 chars, the documented degrade behavior
    assert len(result) == 10


def test_composite_suggest_degrades_to_empty_list_when_all_fail():
    def fake_post_fail(url, body, timeout):
        return {"candidates": []}

    composite = CompositeAIAdapter([GeminiAdapter(api_key="fake-key", http_post=fake_post_fail)])
    assert composite.suggest("some context") == []


# -- answer_question cascade (ADR-050, v3 Phase 7) -----------------------

def test_composite_answer_question_cascades_to_working_provider():
    def fake_post_fail(url, body, timeout):
        return {"candidates": []}

    def fake_post_succeed(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": "The answer is 42."}]}}]}

    failing = GeminiAdapter(api_key="fake-key", http_post=fake_post_fail)
    working = GeminiAdapter(api_key="fake-key", http_post=fake_post_succeed)
    composite = CompositeAIAdapter([failing, working])
    result = composite.answer_question("some document text", "What is the answer?")
    assert result == "The answer is 42."


def test_composite_answer_question_degrades_to_honest_message_when_all_fail():
    """Confirms the cascade's degraded_default for this method is the
    same explicit 'AI not configured' sentence NullAdapter itself
    returns — not the generic 'echo the input back' degrade every
    other _cascade_text call uses, since there's no sensible echo for
    a Q&A answer."""
    def fake_post_fail(url, body, timeout):
        return {"candidates": []}

    composite = CompositeAIAdapter([
        GeminiAdapter(api_key="fake-key", http_post=fake_post_fail),
        GeminiAdapter(api_key="fake-key", http_post=fake_post_fail),
    ])
    result = composite.answer_question("some document text", "a question")
    assert "not configured" in result.lower()


def test_composite_answer_question_no_providers_available():
    class NeverAvailable:
        def is_available(self):
            return False

    composite = CompositeAIAdapter([NeverAvailable()])
    result = composite.answer_question("doc text", "a question")
    assert "not configured" in result.lower()


# -- AIPort invisible-failure logging (ADR-033 regression, other half) --
# Same visibility gap ADR-031 fixed for AIPipelinePort methods existed
# unfixed in AIPort's methods until now — every failure was swallowed
# with zero logging anywhere, Sentry or otherwise.

def test_gemini_propose_structure_logs_on_failure(monkeypatch):
    captured = {}

    def fake_capture_exception(exc, tags=None):
        captured["exc"] = exc
        captured["tags"] = tags

    import backend.adapters.ai.gemini_adapter as mod
    monkeypatch.setattr(mod, "capture_exception", fake_capture_exception)

    def fake_post(url, body, timeout):
        return {"candidates": []}  # triggers a raise inside _generate_text

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    outline = make_outline_for_enhancement()
    result = adapter.propose_structure(outline, "source text")

    assert result is outline  # still degrades safely
    assert captured.get("exc") is not None  # but the failure was NOT silently swallowed
    assert captured["tags"]["method"] == "propose_structure"
    assert captured["tags"]["provider"] == "GeminiAdapter"


def test_gemini_rewrite_logs_on_failure(monkeypatch):
    captured = {}

    def fake_capture_exception(exc, tags=None):
        captured["exc"] = exc

    import backend.adapters.ai.gemini_adapter as mod
    monkeypatch.setattr(mod, "capture_exception", fake_capture_exception)

    def fake_post(url, body, timeout):
        return {"candidates": []}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    result = adapter.rewrite("some text")
    assert result == "some text"
    assert captured.get("exc") is not None


# -- JSON-mode threading for propose_structure (ADR-034 regression) -----
# Production bug: HuggingFace's call succeeded (no HTTP error) but
# _parse_structure_json ... rather _propose_structure_raising failed
# with "model response could not be parsed into a valid outline" —
# json_mode was never actually requested for this one method that
# needs structured output, unlike every AIPipelinePort stage which
# already forced it. Confirmed fix: propose_structure now requests
# json_mode=True; the other four text methods (rewrite/translate/
# summarize/suggest) correctly do NOT, since they want plain text.

def test_gemini_propose_structure_requests_json_mode():
    captured = {}

    def fake_post(url, body, timeout):
        captured["body"] = body
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(
            [{"title": "T", "bullets": ["a"]}]
        )}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.propose_structure(make_outline_for_enhancement(), "source text")
    assert captured["body"]["generationConfig"].get("responseMimeType") == "application/json"


def test_gemini_rewrite_does_not_request_json_mode():
    """rewrite/translate/summarize/suggest want plain text back —
    forcing JSON mode on these would break them, not fix anything."""
    captured = {}

    def fake_post(url, body, timeout):
        captured["body"] = body
        return {"candidates": [{"content": {"parts": [{"text": "A better sentence."}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.rewrite("original text")
    assert "responseMimeType" not in captured["body"]["generationConfig"]


def test_groq_propose_structure_requests_json_mode():
    captured = {}

    def fake_post(url, api_key, body, timeout):
        captured["body"] = body
        return {"choices": [{"message": {"content": json.dumps(
            [{"title": "T", "bullets": ["a"]}]
        )}}]}

    adapter = GroqAdapter(api_key="fake-key", http_post=fake_post)
    adapter.propose_structure(make_outline_for_enhancement(), "source text")
    assert captured["body"].get("response_format") == {"type": "json_object"}


def test_groq_rewrite_does_not_request_json_mode():
    captured = {}

    def fake_post(url, api_key, body, timeout):
        captured["body"] = body
        return {"choices": [{"message": {"content": "A better sentence."}}]}

    adapter = GroqAdapter(api_key="fake-key", http_post=fake_post)
    adapter.rewrite("original text")
    assert "response_format" not in captured["body"]


def test_local_model_propose_structure_requests_json_format():
    captured = {}

    class CapturingHttpClient:
        def get(self, url, timeout):
            return {"status_code": 200}

        def post(self, url, json, timeout):
            captured["json"] = json
            return {"status_code": 200, "json": {"response": '[{"title": "T", "bullets": ["a"]}]'}}

    adapter = LocalModelAdapter(http_client=CapturingHttpClient())
    adapter.propose_structure(make_outline_for_enhancement(), "source text")
    assert captured["json"].get("format") == "json"


def test_local_model_rewrite_does_not_request_json_format():
    captured = {}

    class CapturingHttpClient:
        def get(self, url, timeout):
            return {"status_code": 200}

        def post(self, url, json, timeout):
            captured["json"] = json
            return {"status_code": 200, "json": {"response": "A better sentence."}}

    adapter = LocalModelAdapter(http_client=CapturingHttpClient())
    adapter.rewrite("original text")
    assert "format" not in captured["json"]


# -- Token budget fix (ADR-030 regression) -----------------------------
# Production bug: no provider adapter set an explicit output-token
# limit, so each provider's own (sometimes modest) default silently
# truncated the JSON response once slide count grew — a decks-with-
# more-than-a-few-slides-fall-back-to-deterministic bug, same failure
# SHAPE as the layout off-by-one bug (a hidden assumption that broke
# only past a size threshold). Fixed by always setting an explicit,
# generous, slide-count-scaled token budget.

def test_token_budget_scales_with_slide_count():
    from backend.adapters.ai.json_pipeline_base import _token_budget, _TOKEN_BUDGET_FLOOR, _TOKEN_BUDGET_CEILING
    assert _token_budget(1) == _TOKEN_BUDGET_FLOOR  # small decks hit the floor, not zero
    assert _token_budget(10) > _token_budget(3)  # genuinely scales up
    assert _token_budget(1000) == _TOKEN_BUDGET_CEILING  # capped, never unbounded


def test_gemini_content_call_sets_explicit_max_output_tokens_scaled_to_slide_count():
    captured = {}

    def fake_post(url, body, timeout):
        captured["body"] = body
        return {"candidates": [{"content": {"parts": [{"text": content_json(12)}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.generate_slide_content(make_request(12), make_strategy(), make_structure(12))
    assert "maxOutputTokens" in captured["body"]["generationConfig"]
    # A 12-slide request must get a materially larger budget than the floor —
    # this is the actual fix: no more relying on the provider's own default.
    assert captured["body"]["generationConfig"]["maxOutputTokens"] > 3072


def test_gemini_raises_clear_error_on_truncated_response():
    def fake_post(url, body, timeout):
        return {"candidates": [{
            "content": {"parts": [{"text": '{"slides": [{"title": "Cut off mid'}]},
            "finishReason": "MAX_TOKENS",
        }]}
    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    with pytest.raises(RuntimeError, match="truncated"):
        adapter.generate_strategy(make_request(3))


def test_groq_content_call_sets_explicit_max_tokens_scaled_to_slide_count():
    captured = {}

    def fake_post(url, api_key, body, timeout):
        captured["body"] = body
        return {"choices": [{"message": {"content": content_json(12)}}]}

    adapter = GroqAdapter(api_key="fake-key", http_post=fake_post)
    adapter.generate_slide_content(make_request(12), make_strategy(), make_structure(12))
    assert captured["body"]["max_tokens"] > 3072


def test_groq_raises_clear_error_on_truncated_response():
    def fake_post(url, api_key, body, timeout):
        return {"choices": [{"message": {"content": '{"slides": [{"title": "cut'},
                              "finish_reason": "length"}]}
    adapter = GroqAdapter(api_key="fake-key", http_post=fake_post)
    with pytest.raises(RuntimeError, match="truncated"):
        adapter.generate_strategy(make_request(3))


def test_local_model_content_call_sets_num_predict_scaled_to_slide_count():
    captured = {}

    class CapturingHttpClient:
        def get(self, url, timeout):
            return {"status_code": 200}

        def post(self, url, json, timeout):
            captured["json"] = json
            captured["timeout"] = timeout
            return {"status_code": 200, "json": {"response": content_json(12)}}

    adapter = LocalModelAdapter(http_client=CapturingHttpClient())
    adapter.generate_slide_content(make_request(12), make_strategy(), make_structure(12))
    assert captured["json"]["options"]["num_predict"] > 3072


# -- Read timeout scaling fix (ADR-030 regression #2) -------------------
# Production bug: max_tokens scaled with slide count (fix #1 above),
# but the read timeout stayed a fixed 45s regardless — a bigger token
# budget takes proportionally longer to actually generate, so a
# 10-slide content-generation call was cut off mid-response by the
# unscaled timeout. Caught live via a real TimeoutError in production
# logs. Fixed by scaling the timeout the same way, from the same
# slide_count input, so the two can't drift out of proportion again.

def test_read_timeout_scales_with_slide_count():
    from backend.adapters.ai.json_pipeline_base import _read_timeout, _READ_TIMEOUT_FLOOR, _READ_TIMEOUT_CEILING
    assert _read_timeout(1) == _READ_TIMEOUT_FLOOR
    assert _read_timeout(10) > _read_timeout(3)
    assert _read_timeout(1000) == _READ_TIMEOUT_CEILING


def test_gemini_content_call_uses_scaled_timeout_not_fixed_45s():
    captured = {}

    def fake_post(url, body, timeout):
        captured["timeout"] = timeout
        return {"candidates": [{"content": {"parts": [{"text": content_json(12)}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.generate_slide_content(make_request(12), make_strategy(), make_structure(12))
    # A 12-slide request must get more time than the old fixed 45s —
    # this is the actual fix.
    assert captured["timeout"] > 45


def test_groq_content_call_uses_scaled_timeout_not_fixed_45s():
    captured = {}

    def fake_post(url, api_key, body, timeout):
        captured["timeout"] = timeout
        return {"choices": [{"message": {"content": content_json(12)}}]}

    adapter = GroqAdapter(api_key="fake-key", http_post=fake_post)
    adapter.generate_slide_content(make_request(12), make_strategy(), make_structure(12))
    assert captured["timeout"] > 45


def test_local_model_content_call_uses_scaled_timeout_not_fixed_default():
    captured = {}

    class CapturingHttpClient:
        def get(self, url, timeout):
            return {"status_code": 200}

        def post(self, url, json, timeout):
            captured["timeout"] = timeout
            return {"status_code": 200, "json": {"response": content_json(12)}}

    adapter = LocalModelAdapter(http_client=CapturingHttpClient())
    adapter.generate_slide_content(make_request(12), make_strategy(), make_structure(12))
    assert captured["timeout"] > 45


def test_small_deck_still_uses_reasonable_fast_timeout():
    """A 3-slide strategy call shouldn't wait the full ceiling — the
    floor keeps small requests responsive."""
    captured = {}

    def fake_post(url, body, timeout):
        captured["timeout"] = timeout
        return {"candidates": [{"content": {"parts": [{"text": strategy_json()}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.generate_strategy(make_request(3))
    assert captured["timeout"] == 45  # floor, unchanged for small requests


# -- Slide-level editing / partial regeneration (ADR-038) ----------------

def make_regen_context(instructions=None):
    return SlideRegenerationContext(
        topic_or_source_summary="Topic: Climate Change",
        audience_type="general",
        language="en",
        other_slide_titles=["Introduction", "Causes", "Conclusion"],
        current_title="Effects on Agriculture",
        current_bullets=["Crop yields declining", "Water scarcity increasing"],
        current_notes="Discuss regional variation.",
        instructions=instructions,
    )


def regen_response_json(title="Effects on Global Food Security", bullets=None, notes="Updated notes."):
    return json.dumps({
        "title": title,
        "bullets": bullets or ["Crop yields declining in key regions", "Rising water scarcity"],
        "speaker_notes": notes,
    })


def test_gemini_regenerate_slide_returns_new_content():
    adapter = gemini_with(regen_response_json())
    title, bullets, notes = adapter.regenerate_slide(make_regen_context())
    assert title == "Effects on Global Food Security"
    assert len(bullets) == 2
    assert notes == "Updated notes."


def test_gemini_regenerate_slide_includes_instructions_in_prompt():
    captured = {}

    def fake_post(url, body, timeout):
        captured["prompt"] = body["contents"][0]["parts"][0]["text"]
        return {"candidates": [{"content": {"parts": [{"text": regen_response_json()}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.regenerate_slide(make_regen_context(instructions="make this more concise"))
    assert "make this more concise" in captured["prompt"]


def test_gemini_regenerate_slide_includes_other_titles_for_consistency():
    captured = {}

    def fake_post(url, body, timeout):
        captured["prompt"] = body["contents"][0]["parts"][0]["text"]
        return {"candidates": [{"content": {"parts": [{"text": regen_response_json()}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.regenerate_slide(make_regen_context())
    assert "Introduction" in captured["prompt"]
    assert "Causes" in captured["prompt"]
    assert "Conclusion" in captured["prompt"]


def test_gemini_regenerate_slide_raises_on_missing_title():
    adapter = gemini_with(json.dumps({"bullets": ["a"], "speaker_notes": "n"}))
    with pytest.raises(ValueError):
        adapter.regenerate_slide(make_regen_context())


def test_gemini_regenerate_slide_raises_on_empty_bullets():
    adapter = gemini_with(json.dumps({"title": "T", "bullets": [], "speaker_notes": "n"}))
    with pytest.raises(ValueError):
        adapter.regenerate_slide(make_regen_context())


def test_composite_regenerate_slide_cascades_to_working_provider():
    failing = AlwaysFailsAdapter()
    working = gemini_with(regen_response_json())
    # AlwaysFailsAdapter only raises on generate_strategy — give it a
    # regenerate_slide that also fails, matching the class's purpose.
    failing.regenerate_slide = lambda context: (_ for _ in ()).throw(RuntimeError("fail"))
    composite = CompositeAIAdapter([failing, working])
    title, bullets, notes = composite.regenerate_slide(make_regen_context())
    assert title == "Effects on Global Food Security"


# -- Format-aware content generation (ADR-054) ------------------------------
# Before this, _build_content_prompt always asked for terse slide-bullet
# fragments regardless of export_format — the literal reason a generated
# "document" read like a reformatted deck instead of a real document.

def test_content_prompt_asks_for_prose_paragraphs_for_document_docx():
    adapter = gemini_with(content_json())
    request = GenerationRequest(topic="Photosynthesis", slide_count=3, export_format="document_docx")
    prompt = adapter._build_content_prompt(request, make_strategy(), make_structure())
    assert "paragraph" in prompt.lower()
    assert "not a bullet list" in prompt.lower()
    assert "terminal punctuation" in prompt.lower()


def test_content_prompt_asks_for_bullets_for_pptx():
    adapter = gemini_with(content_json())
    request = GenerationRequest(topic="Photosynthesis", slide_count=3, export_format="pptx")
    prompt = adapter._build_content_prompt(request, make_strategy(), make_structure())
    assert "bullet point" in prompt.lower()
    assert "paragraph" not in prompt.lower() or "not a paragraph" in prompt.lower()


def test_content_prompt_asks_for_prose_for_document_pdf():
    """ADR-055 — document_pdf shares document_docx's prose branch (the
    two document formats differ only in the export adapter, never in
    content), so it should get the exact same prompt shape."""
    adapter = gemini_with(content_json())
    request = GenerationRequest(topic="Photosynthesis", slide_count=3, export_format="document_pdf")
    prompt = adapter._build_content_prompt(request, make_strategy(), make_structure())
    assert "paragraph" in prompt.lower()
    assert "not a bullet list" in prompt.lower()
    assert "terminal punctuation" in prompt.lower()


def test_content_prompt_defaults_to_pptx_bullets_when_export_format_unset():
    """GenerationRequest.export_format defaults to 'pptx', so any call
    site that never learned about ADR-054 keeps its exact prior
    behavior — this proves the default, not just that document_docx
    works when explicitly requested."""
    adapter = gemini_with(content_json())
    request = GenerationRequest(topic="Photosynthesis", slide_count=3)  # export_format not set
    prompt = adapter._build_content_prompt(request, make_strategy(), make_structure())
    assert "bullet point" in prompt.lower()


def test_document_docx_content_is_not_truncated_at_the_slide_bullet_length():
    """MAX_BULLET_LENGTH (160 chars) is sized for a slide-bullet
    fragment and would cut a real multi-sentence paragraph off
    mid-sentence, destroying the trailing punctuation the document
    renderer's paragraph-vs-list detection depends on. A long,
    genuinely realistic paragraph must survive intact."""
    long_paragraph = (
        "Solar power costs have dropped by roughly eighty percent over the past decade, "
        "making it the cheapest source of new electricity generation in most markets "
        "worldwide, a trend driven by manufacturing scale, improved panel efficiency, "
        "and falling costs for supporting infrastructure such as inverters and racking."
    )
    assert len(long_paragraph) > 160  # confirms this test actually exercises the old limit
    response = json.dumps({"slides": [
        {"title": "Slide 1", "bullets": [long_paragraph], "speaker_notes": "n"},
    ]})
    adapter = gemini_with(response)
    request = GenerationRequest(topic="Solar", slide_count=1, export_format="document_docx")
    outline = adapter.generate_slide_content(request, make_strategy(), make_structure(1))
    stored_text = outline.slides[0].content_blocks[0].text
    assert stored_text == long_paragraph  # survived whole, including the trailing period
    assert stored_text.endswith(".")


def test_pptx_content_is_still_truncated_at_the_original_bullet_length():
    """The document-mode length increase must not leak into every
    other format — pptx (and everything else) keeps the original,
    deliberately-short fragment ceiling."""
    long_text = "x" * 300
    response = json.dumps({"slides": [
        {"title": "Slide 1", "bullets": [long_text], "speaker_notes": "n"},
    ]})
    adapter = gemini_with(response)
    request = GenerationRequest(topic="Test", slide_count=1, export_format="pptx")
    outline = adapter.generate_slide_content(request, make_strategy(), make_structure(1))
    stored_text = outline.slides[0].content_blocks[0].text
    assert len(stored_text) == 160  # MAX_BULLET_LENGTH, unchanged for this format

