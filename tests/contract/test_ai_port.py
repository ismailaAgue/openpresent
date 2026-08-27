import json
import pytest
from backend.adapters.ai.null_adapter import NullAdapter
from backend.adapters.ai.local_model import LocalModelAdapter
from backend.models.recipe import Outline, Slide, StructureSource


class FakeHttpClient:
    """Test double — lets us verify LocalModelAdapter's request/response
    handling without a real model server running."""

    def __init__(self, tags_status=200, generate_status=200, generate_response=""):
        self.tags_status = tags_status
        self.generate_status = generate_status
        self.generate_response = generate_response
        self.unreachable = False

    def get(self, url, timeout):
        if self.unreachable:
            raise ConnectionError("simulated: model server unreachable")
        return {"status_code": self.tags_status}

    def post(self, url, json, timeout):
        if self.unreachable:
            raise ConnectionError("simulated: model server unreachable")
        return {"status_code": self.generate_status, "json": {"response": self.generate_response}}


def make_outline():
    return Outline(structure_source=StructureSource.RULE_BASED, slides=[
        Slide(order=1, title="Intro", content_blocks=[]),
    ])


# -- NullAdapter: must always be available=False and pass everything through --

def test_null_adapter_always_unavailable():
    assert NullAdapter().is_available() is False


def test_null_adapter_passes_outline_through_unmodified():
    outline = make_outline()
    result = NullAdapter().propose_structure(outline, "some text")
    assert result is outline


def test_null_adapter_answer_question_returns_honest_unavailable_message():
    """The one AIPort method with no meaningful non-AI degradation —
    NullAdapter must say so explicitly, not return an empty string or
    silently echo the question/context back."""
    answer = NullAdapter().answer_question("some document text", "What does this say?")
    assert "not configured" in answer.lower()
    assert answer != ""
    assert answer != "some document text"  # not an echo of the context
    assert answer != "What does this say?"  # not an echo of the question


# -- LocalModelAdapter: unreachable server -> graceful degradation, never raises --

def test_local_model_unreachable_reports_unavailable():
    client = FakeHttpClient()
    client.unreachable = True
    adapter = LocalModelAdapter(http_client=client)
    assert adapter.is_available() is False


def test_local_model_unreachable_falls_back_on_all_methods():
    client = FakeHttpClient()
    client.unreachable = True
    adapter = LocalModelAdapter(http_client=client)
    outline = make_outline()

    assert adapter.propose_structure(outline, "text") is outline
    assert adapter.rewrite("hello") == "hello"
    assert adapter.translate("hello", "fr") == "hello"
    assert adapter.summarize("hello world", max_length=5) == "hello"
    assert adapter.suggest("context") == []
    assert "not configured" in adapter.answer_question("doc text", "question?").lower()


# -- LocalModelAdapter: reachable, well-formed response --

def test_local_model_available_when_server_healthy():
    client = FakeHttpClient(tags_status=200)
    adapter = LocalModelAdapter(http_client=client)
    assert adapter.is_available() is True


def test_local_model_parses_valid_outline_response():
    good_response = json.dumps([
        {"title": "Better Intro", "bullets": ["point one", "point two"]},
    ])
    client = FakeHttpClient(generate_response=good_response)
    adapter = LocalModelAdapter(http_client=client)
    result = adapter.propose_structure(make_outline(), "source text")
    assert result.structure_source == StructureSource.AI_ENHANCED
    assert result.slides[0].title == "Better Intro"


def test_local_model_malformed_response_falls_back_to_baseline():
    client = FakeHttpClient(generate_response="not valid json at all")
    adapter = LocalModelAdapter(http_client=client)
    outline = make_outline()
    result = adapter.propose_structure(outline, "source text")
    assert result is outline  # discarded the bad AI output, kept the rule-based baseline


def test_local_model_server_error_falls_back_to_baseline():
    client = FakeHttpClient(generate_status=500)
    adapter = LocalModelAdapter(http_client=client)
    outline = make_outline()
    result = adapter.propose_structure(outline, "source text")
    assert result is outline


# -- answer_question (ADR-050, v3 Phase 7) -------------------------------

def test_local_model_answer_question_returns_model_response_when_available():
    client = FakeHttpClient(generate_response="The three stages are evaporation, condensation, and precipitation.")
    adapter = LocalModelAdapter(http_client=client)
    answer = adapter.answer_question("The water cycle has three stages...", "What are the stages?")
    assert answer == "The three stages are evaporation, condensation, and precipitation."


def test_local_model_answer_question_degrades_on_server_error():
    """Unlike rewrite/translate/summarize (which fall back to the
    unmodified input), there's no sensible 'unmodified input' for a
    Q&A answer — the degraded response must be an honest statement
    that the provider failed, not an empty string or a raised
    exception reaching the caller."""
    client = FakeHttpClient(generate_status=500)
    adapter = LocalModelAdapter(http_client=client)
    answer = adapter.answer_question("doc text", "a question")
    assert answer != ""
    assert "couldn't" in answer.lower() or "not configured" in answer.lower()


def test_local_model_answer_question_degrades_on_empty_model_response():
    client = FakeHttpClient(generate_response="")
    adapter = LocalModelAdapter(http_client=client)
    answer = adapter.answer_question("doc text", "a question")
    assert answer != ""  # never surfaces a blank answer to the caller
