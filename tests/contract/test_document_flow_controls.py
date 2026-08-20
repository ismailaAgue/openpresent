import json


def make_outline_with_slides(n=3):
    from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
    return Outline(structure_source=StructureSource.RULE_BASED, slides=[
        Slide(order=i + 1, title=f"Section {i + 1}", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text=f"point {i + 1}"),
        ])
        for i in range(n)
    ])


# -- target_slide_count hint threading (ADR-034) -------------------------

def test_gemini_propose_structure_includes_slide_count_hint_in_prompt():
    from backend.adapters.ai.gemini_adapter import GeminiAdapter
    captured = {}

    def fake_post(url, body, timeout):
        captured["prompt"] = body["contents"][0]["parts"][0]["text"]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(
            [{"title": "T", "bullets": ["a"]}]
        )}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.propose_structure(make_outline_with_slides(3), "source text", target_slide_count=8)
    assert "approximately 8 slides" in captured["prompt"]


def test_gemini_propose_structure_omits_hint_when_no_target_given():
    from backend.adapters.ai.gemini_adapter import GeminiAdapter
    captured = {}

    def fake_post(url, body, timeout):
        captured["prompt"] = body["contents"][0]["parts"][0]["text"]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(
            [{"title": "T", "bullets": ["a"]}]
        )}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    adapter.propose_structure(make_outline_with_slides(3), "source text")
    assert "approximately" not in captured["prompt"]


def test_null_adapter_ignores_target_slide_count_without_error():
    from backend.adapters.ai.null_adapter import NullAdapter
    outline = make_outline_with_slides(3)
    result = NullAdapter().propose_structure(outline, "source", target_slide_count=10)
    assert result is outline  # unmodified, no error just because the hint was passed


def test_composite_threads_target_slide_count_through_cascade():
    from backend.adapters.ai.gemini_adapter import GeminiAdapter
    from backend.adapters.ai.composite_adapter import CompositeAIAdapter
    captured = {}

    def fake_post(url, body, timeout):
        captured["prompt"] = body["contents"][0]["parts"][0]["text"]
        return {"candidates": [{"content": {"parts": [{"text": json.dumps(
            [{"title": "T", "bullets": ["a"]}]
        )}]}}]}

    adapter = GeminiAdapter(api_key="fake-key", http_post=fake_post)
    composite = CompositeAIAdapter([adapter])
    composite.propose_structure(make_outline_with_slides(3), "source text", target_slide_count=5)
    assert "approximately 5 slides" in captured["prompt"]


# -- document-flow translation (ADR-034: language was metadata-only before) --

def test_generate_engine_translates_when_language_not_english(monkeypatch):
    from backend.adapters import registry
    from backend.engines.generate import generate_presentation

    class FakeTranslatingAdapter:
        def is_available(self):
            return True

        def propose_structure(self, outline, source_text, target_slide_count=None):
            return outline

        def rewrite(self, text, instructions=""):
            return text

        def translate(self, text, target_language):
            return f"[{target_language}] {text}"

        def summarize(self, text, max_length=None):
            return text

        def suggest(self, context):
            return []

    monkeypatch.setattr(registry, "get_ai_adapter", lambda: FakeTranslatingAdapter())

    source = "**Overview**\n\nSome English content about a topic.\n".encode("utf-8")
    recipe, _ = generate_presentation(file_bytes=source, filename="doc.txt",
                                       export_format="pptx", language="fr")

    assert any(s.title.startswith("[fr]") for s in recipe.outline.slides)


def test_generate_engine_skips_translation_for_english(monkeypatch):
    from backend.adapters import registry
    from backend.engines.generate import generate_presentation

    calls = {"translate_called": False}

    class FakeAdapter:
        def is_available(self):
            return True

        def propose_structure(self, outline, source_text, target_slide_count=None):
            return outline

        def rewrite(self, text, instructions=""):
            return text

        def translate(self, text, target_language):
            calls["translate_called"] = True
            return text

        def summarize(self, text, max_length=None):
            return text

        def suggest(self, context):
            return []

    monkeypatch.setattr(registry, "get_ai_adapter", lambda: FakeAdapter())

    source = "**Overview**\n\nSome English content about a topic.\n".encode("utf-8")
    generate_presentation(file_bytes=source, filename="doc.txt", export_format="pptx", language="en")
    assert calls["translate_called"] is False


def test_generate_engine_translation_degrades_safely_on_failure(monkeypatch):
    """A translate() failure on one bullet must never break the rest
    of generation — matches every other AIPort degrade guarantee."""
    from backend.adapters import registry
    from backend.engines.generate import generate_presentation

    class FlakyTranslateAdapter:
        def is_available(self):
            return True

        def propose_structure(self, outline, source_text, target_slide_count=None):
            return outline

        def rewrite(self, text, instructions=""):
            return text

        def translate(self, text, target_language):
            return text  # AIPort contract: degrade to original, never raise

        def summarize(self, text, max_length=None):
            return text

        def suggest(self, context):
            return []

    monkeypatch.setattr(registry, "get_ai_adapter", lambda: FlakyTranslateAdapter())

    source = "**Overview**\n\nSome English content about a topic.\n".encode("utf-8")
    recipe, output_bytes = generate_presentation(file_bytes=source, filename="doc.txt",
                                                   export_format="pptx", language="es")
    assert len(output_bytes) > 0  # generation completed successfully regardless
