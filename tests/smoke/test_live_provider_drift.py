"""
Live provider drift detection — ADR-036.

NOT part of the hermetic test suite (tests/contract/, tests/integration/).
These tests make REAL network calls to REAL provider APIs using REAL
credentials from environment variables. They exist to catch exactly
the class of bug fixed live in ADR-034 — a stale model name, a
deprecated endpoint, a changed response shape, a provider silently
requiring a param this codebase doesn't send — BEFORE a real user
generation hits it and it has to be diagnosed from production logs
after the fact.

Every test is SKIPPED (not failed, not errored) when its required API
key isn't set in the environment — safe to run anywhere, including a
laptop with only a couple of keys configured, or this sandboxed
environment with none at all. In CI, this suite only runs on a
schedule via .github/workflows/provider-drift-check.yml (not on every
push, unlike the hermetic suite), using secrets configured in the
repo's GitHub Actions settings — third-party API availability should
never block a code push.

Each test exercises the REAL adapter class's REAL method (not a
reimplemented HTTP call) at the cheapest reasonable cost (minimal
prompts, smallest sensible slide counts, single search queries) —
the goal is to catch drift in exactly the code path a real generation
would hit, not to do a comprehensive live-quality audit. If a test
here fails, the fix is almost always the same shape as ADR-034: check
the actual error message (which these tests print via pytest's normal
assertion-failure output), update whatever config/default broke, add
a regression test to the HERMETIC suite once the exact new failure
mode is understood — that part still doesn't belong here.
"""

import os
import pytest


def _require_env(var: str):
    if not os.environ.get(var):
        pytest.skip(f"{var} not set — skipping live check (this is expected, not a failure, "
                     f"in any environment without this key configured)")


# -- AI providers: one cheap Strategy call + one propose_structure call --
# (two different methods because they're two genuinely different code
# paths with their own separate history of drift — ADR-034's Bug 4
# was specific to propose_structure and would NOT have been caught by
# testing generate_strategy alone).

def _make_generation_request():
    from backend.ports.ai_pipeline import GenerationRequest
    return GenerationRequest(topic="The water cycle", slide_count=3, audience_type="general")


def _make_tiny_outline():
    from backend.models.recipe import Outline, Slide, ContentBlock, BlockType, StructureSource
    return Outline(structure_source=StructureSource.RULE_BASED, slides=[
        Slide(order=1, title="The Water Cycle", content_blocks=[
            ContentBlock(type=BlockType.BULLET, text="Water moves between earth and sky"),
        ]),
    ])


class TestGeminiLive:
    def setup_method(self):
        _require_env("GEMINI_API_KEY")

    def test_strategy_call_succeeds(self):
        from backend.adapters.ai.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter(api_key=os.environ["GEMINI_API_KEY"])
        strategy = adapter.generate_strategy(_make_generation_request())
        assert strategy.narrative_style

    def test_propose_structure_call_succeeds(self):
        from backend.adapters.ai.gemini_adapter import GeminiAdapter
        adapter = GeminiAdapter(api_key=os.environ["GEMINI_API_KEY"])
        result = adapter._propose_structure_raising(_make_tiny_outline(), "The water cycle moves "
                                                      "water between oceans, clouds, and rain.")
        assert result.slides


class TestGroqLive:
    def setup_method(self):
        _require_env("GROQ_API_KEY")

    def test_strategy_call_succeeds(self):
        from backend.adapters.ai.groq_adapter import GroqAdapter
        adapter = GroqAdapter(api_key=os.environ["GROQ_API_KEY"])
        strategy = adapter.generate_strategy(_make_generation_request())
        assert strategy.narrative_style

    def test_propose_structure_call_succeeds(self):
        from backend.adapters.ai.groq_adapter import GroqAdapter
        adapter = GroqAdapter(api_key=os.environ["GROQ_API_KEY"])
        result = adapter._propose_structure_raising(_make_tiny_outline(), "The water cycle moves "
                                                      "water between oceans, clouds, and rain.")
        assert result.slides


class TestOpenRouterLive:
    def setup_method(self):
        _require_env("OPENROUTER_API_KEY")

    def test_strategy_call_succeeds(self):
        from backend.adapters.ai.openrouter_adapter import OpenRouterAdapter
        adapter = OpenRouterAdapter(api_key=os.environ["OPENROUTER_API_KEY"])
        strategy = adapter.generate_strategy(_make_generation_request())
        assert strategy.narrative_style


class TestHuggingFaceLive:
    def setup_method(self):
        _require_env("HUGGINGFACE_API_KEY")

    def test_strategy_call_succeeds(self):
        from backend.adapters.ai.huggingface_adapter import HuggingFaceAdapter
        adapter = HuggingFaceAdapter(api_key=os.environ["HUGGINGFACE_API_KEY"])
        strategy = adapter.generate_strategy(_make_generation_request())
        assert strategy.narrative_style

    def test_propose_structure_call_succeeds(self):
        """This exact method, on this exact provider, is what ADR-034's
        Bug 4 was — the one prior live failure this smoke suite would
        have caught before a real document upload hit it."""
        from backend.adapters.ai.huggingface_adapter import HuggingFaceAdapter
        adapter = HuggingFaceAdapter(api_key=os.environ["HUGGINGFACE_API_KEY"])
        result = adapter._propose_structure_raising(_make_tiny_outline(), "The water cycle moves "
                                                      "water between oceans, clouds, and rain.")
        assert result.slides


# -- Image providers: one cheap search + fetch per provider --------------

class TestUnsplashLive:
    def setup_method(self):
        _require_env("OPENPRESENT_UNSPLASH_ACCESS_KEY")

    def test_search_and_fetch_succeeds(self):
        from backend.adapters.media.unsplash_adapter import UnsplashProvider
        provider = UnsplashProvider(access_key=os.environ["OPENPRESENT_UNSPLASH_ACCESS_KEY"])
        candidates = provider.search_candidates("mountains", per_page=1)
        assert candidates, "Unsplash returned zero candidates for a common query"
        image_bytes = provider.fetch_bytes(candidates[0])
        assert image_bytes and len(image_bytes) > 100


class TestPexelsLive:
    def setup_method(self):
        _require_env("OPENPRESENT_PEXELS_API_KEY")

    def test_search_and_fetch_succeeds(self):
        from backend.adapters.media.pexels_adapter import PexelsProvider
        provider = PexelsProvider(api_key=os.environ["OPENPRESENT_PEXELS_API_KEY"])
        candidates = provider.search_candidates("mountains", per_page=1)
        assert candidates, "Pexels returned zero candidates for a common query"
        image_bytes = provider.fetch_bytes(candidates[0])
        assert image_bytes and len(image_bytes) > 100


class TestPixabayLive:
    def setup_method(self):
        _require_env("OPENPRESENT_PIXABAY_API_KEY")

    def test_search_and_fetch_succeeds(self):
        from backend.adapters.media.pixabay_adapter import PixabayProvider
        provider = PixabayProvider(api_key=os.environ["OPENPRESENT_PIXABAY_API_KEY"])
        candidates = provider.search_candidates("mountains", per_page=1)
        assert candidates, "Pixabay returned zero candidates for a common query"
        image_bytes = provider.fetch_bytes(candidates[0])
        assert image_bytes and len(image_bytes) > 100


def test_wikimedia_search_and_fetch_succeeds():
    """No key needed — always runs. This is the universal image
    fallback; if THIS breaks, every deployment with zero image keys
    configured loses images entirely, which makes drift here more
    urgent to catch than the keyed providers above."""
    from backend.adapters.media.wikimedia_adapter import WikimediaProvider
    provider = WikimediaProvider()
    candidates = provider.search_candidates("mountains", per_page=1)
    assert candidates, "Wikimedia Commons returned zero candidates for a common query"
    image_bytes = provider.fetch_bytes(candidates[0])
    assert image_bytes and len(image_bytes) > 100


# -- Research providers ---------------------------------------------------

class TestTavilyLive:
    def setup_method(self):
        _require_env("TAVILY_API_KEY")

    def test_research_call_succeeds(self):
        from backend.adapters.research.tavily_research import TavilyResearchAdapter
        adapter = TavilyResearchAdapter(api_key=os.environ["TAVILY_API_KEY"])
        brief = adapter.research("photosynthesis")
        assert brief.facts, "Tavily returned zero facts for a well-known topic"


class TestBraveSearchLive:
    def setup_method(self):
        _require_env("BRAVE_SEARCH_API_KEY")

    def test_research_call_succeeds(self):
        from backend.adapters.research.brave_research import BraveSearchResearchAdapter
        adapter = BraveSearchResearchAdapter(api_key=os.environ["BRAVE_SEARCH_API_KEY"])
        brief = adapter.research("photosynthesis")
        assert brief.facts, "Brave Search returned zero facts for a well-known topic"


def test_wikipedia_research_call_succeeds():
    """No key needed — always runs, same universal-fallback urgency
    argument as the Wikimedia image test above."""
    from backend.adapters.research.wikipedia_research import WikipediaResearchAdapter
    adapter = WikipediaResearchAdapter()
    brief = adapter.research("photosynthesis")
    assert brief.facts, "Wikipedia REST API returned zero facts for a well-known topic"
