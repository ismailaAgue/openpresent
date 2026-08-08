import json
import pytest
from backend.adapters.ai.gemini_adapter import GeminiAdapter
from backend.adapters.ai.local_model import LocalModelAdapter
from backend.ports.ai_pipeline import GenerationRequest
from backend.models.recipe import StructureSource


def make_request(slide_count=3):
    return GenerationRequest(topic="Photosynthesis", slide_count=slide_count,
                              audience_type="student_school", language="en")


def good_outline_json(n=3):
    return json.dumps({"slides": [
        {"title": f"Slide {i+1}", "bullets": [f"point {i+1}a", f"point {i+1}b"],
         "speaker_notes": f"notes for slide {i+1}"}
        for i in range(n)
    ]})


# -- GeminiAdapter: availability is key-presence only, never a network call --

def test_gemini_unavailable_without_key():
    assert GeminiAdapter(api_key="").is_available() is False


def test_gemini_available_with_key_no_network_call():
    calls = []

    def fake_post(url, body, timeout):
        calls.append(url)
        raise AssertionError("is_available() must not make a network call")

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    assert adapter.is_available() is True
    assert calls == []  # confirms no network call happened


def test_gemini_generates_outline_from_well_formed_response():
    def fake_post(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": good_outline_json(3)}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    outline = adapter.generate_presentation_outline(make_request(3))
    assert outline.structure_source == StructureSource.AI_GENERATED
    assert len(outline.slides) == 3
    assert outline.slides[0].title == "Slide 1"


def test_gemini_raises_on_wrong_slide_count_engine_falls_back():
    def fake_post(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": good_outline_json(2)}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    with pytest.raises(ValueError):
        adapter.generate_presentation_outline(make_request(3))  # asked for 3, got 2


def test_gemini_strips_markdown_fences():
    fenced = "```json\n" + good_outline_json(3) + "\n```"

    def fake_post(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": fenced}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    outline = adapter.generate_presentation_outline(make_request(3))
    assert len(outline.slides) == 3


def test_gemini_raises_on_blocked_response():
    def fake_post(url, body, timeout):
        return {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    with pytest.raises(RuntimeError):
        adapter.generate_presentation_outline(make_request(3))


def test_gemini_trims_excess_bullets_and_length():
    long_text = "x" * 500
    raw = json.dumps({"slides": [
        {"title": "T", "bullets": [long_text] * 10, "speaker_notes": long_text}
    ]})

    def fake_post(url, body, timeout):
        return {"candidates": [{"content": {"parts": [{"text": raw}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    outline = adapter.generate_presentation_outline(make_request(1))
    bullets = [b for b in outline.slides[0].content_blocks]
    # bullets capped at 6, plus 1 note block = at most 7 blocks
    assert len(bullets) <= 7
    assert all(len(b.text) <= 700 for b in bullets)


# -- LocalModelAdapter also implements the pipeline port (ADR-028) ------

class FakeHttpClient:
    def __init__(self, tags_status=200, generate_response=""):
        self.tags_status = tags_status
        self.generate_response = generate_response

    def get(self, url, timeout):
        return {"status_code": self.tags_status}

    def post(self, url, json, timeout):
        return {"status_code": 200, "json": {"response": self.generate_response}}


def test_local_model_generates_topic_outline_when_reachable():
    client = FakeHttpClient(generate_response=good_outline_json(3))
    adapter = LocalModelAdapter(http_client=client)
    outline = adapter.generate_presentation_outline(make_request(3))
    assert outline.structure_source == StructureSource.AI_GENERATED
    assert len(outline.slides) == 3


def test_local_model_pipeline_raises_when_unreachable():
    client = FakeHttpClient(tags_status=500)
    adapter = LocalModelAdapter(http_client=client)
    with pytest.raises(Exception):
        adapter.generate_presentation_outline(make_request(3))
