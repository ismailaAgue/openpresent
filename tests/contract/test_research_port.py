from backend.adapters.research.null_research import NullResearchAdapter
from backend.adapters.research.duckduckgo_research import DuckDuckGoResearchAdapter

SAMPLE_HTML = """
<html><body><table>
<tr><td class="result-snippet">Photosynthesis converts light energy into chemical energy stored in glucose.</td></tr>
<tr><td class="result-snippet">The process occurs primarily in the chloroplasts of plant cells.</td></tr>
</table></body></html>
"""


class FakeHttpClient:
    def __init__(self, status=200, content=SAMPLE_HTML.encode("utf-8")):
        self.status = status
        self.content = content

    def get(self, url, headers=None, timeout=10):
        return {"status_code": self.status, "content": self.content}


def test_null_research_always_unavailable():
    assert NullResearchAdapter().is_available() is False


def test_null_research_returns_empty_brief():
    brief = NullResearchAdapter().research("anything")
    assert brief.facts == []
    assert brief.sources == []


def test_duckduckgo_always_available():
    assert DuckDuckGoResearchAdapter(http_client=FakeHttpClient()).is_available() is True


def test_duckduckgo_extracts_facts_from_snippets():
    adapter = DuckDuckGoResearchAdapter(http_client=FakeHttpClient())
    brief = adapter.research("photosynthesis")
    assert len(brief.facts) == 2
    assert "chloroplasts" in brief.facts[1]
    assert brief.sources  # non-empty when facts were found


def test_duckduckgo_returns_empty_brief_on_empty_topic():
    adapter = DuckDuckGoResearchAdapter(http_client=FakeHttpClient())
    brief = adapter.research("   ")
    assert brief.facts == []


def test_duckduckgo_returns_empty_brief_on_http_failure():
    adapter = DuckDuckGoResearchAdapter(http_client=FakeHttpClient(status=500))
    brief = adapter.research("photosynthesis")
    assert brief.facts == []


def test_duckduckgo_never_raises_on_broken_client():
    class BrokenClient:
        def get(self, *a, **k):
            raise ConnectionError("simulated failure")
    adapter = DuckDuckGoResearchAdapter(http_client=BrokenClient())
    brief = adapter.research("photosynthesis")
    assert brief.facts == []


# -- WikipediaResearchAdapter (ADR-032: free, no-key, real REST API,
# replaces DuckDuckGo scraping as the default free fallback) ----------

class FakeWikipediaHttpClient:
    def __init__(self, search_status=200, summary_status=200,
                 search_json=None, summary_json=None):
        self.search_status = search_status
        self.summary_status = summary_status
        self.search_json = search_json if search_json is not None else {
            "query": {"search": [{"title": "Photosynthesis"}]}
        }
        self.summary_json = summary_json if summary_json is not None else {
            "extract": "Photosynthesis converts light into chemical energy. "
                       "It occurs in chloroplasts.",
            "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Photosynthesis"}},
        }

    def get(self, url, timeout=10, headers=None):
        if "action=query" in url:
            return {"status_code": self.search_status, "json": self.search_json}
        return {"status_code": self.summary_status, "json": self.summary_json}


def test_wikipedia_always_available():
    from backend.adapters.research.wikipedia_research import WikipediaResearchAdapter
    assert WikipediaResearchAdapter(http_client=FakeWikipediaHttpClient()).is_available() is True


def test_wikipedia_returns_sentence_level_facts():
    from backend.adapters.research.wikipedia_research import WikipediaResearchAdapter
    adapter = WikipediaResearchAdapter(http_client=FakeWikipediaHttpClient())
    brief = adapter.research("photosynthesis")
    assert len(brief.facts) == 2
    assert "chloroplasts" in brief.facts[1]
    assert brief.sources == ["https://en.wikipedia.org/wiki/Photosynthesis"]


def test_wikipedia_returns_empty_brief_when_no_article_found():
    from backend.adapters.research.wikipedia_research import WikipediaResearchAdapter
    adapter = WikipediaResearchAdapter(
        http_client=FakeWikipediaHttpClient(search_json={"query": {"search": []}})
    )
    brief = adapter.research("asdkjfhaslkdjfh nonsense topic")
    assert brief.facts == []


def test_wikipedia_never_raises_on_broken_client():
    from backend.adapters.research.wikipedia_research import WikipediaResearchAdapter

    class BrokenClient:
        def get(self, *a, **k):
            raise ConnectionError("simulated failure")

    adapter = WikipediaResearchAdapter(http_client=BrokenClient())
    brief = adapter.research("photosynthesis")
    assert brief.facts == []


# -- TavilyResearchAdapter (ADR-032: purpose-built for LLM grounding) --

def test_tavily_unavailable_without_key():
    from backend.adapters.research.tavily_research import TavilyResearchAdapter
    assert TavilyResearchAdapter(api_key="").is_available() is False


def test_tavily_extracts_answer_and_result_content():
    from backend.adapters.research.tavily_research import TavilyResearchAdapter

    def fake_post(url, body, timeout):
        return {
            "answer": "Photosynthesis is how plants convert light to energy.",
            "results": [
                {"content": "It happens in chloroplasts.", "url": "https://example.com/a"},
                {"content": "Chlorophyll absorbs the light.", "url": "https://example.com/b"},
            ],
        }

    adapter = TavilyResearchAdapter(api_key="fake-key", http_post=fake_post)
    brief = adapter.research("photosynthesis")
    assert brief.facts[0] == "Photosynthesis is how plants convert light to energy."
    assert "chloroplasts" in brief.facts[1]
    assert brief.sources == ["https://example.com/a", "https://example.com/b"]


def test_tavily_never_raises_on_broken_client():
    from backend.adapters.research.tavily_research import TavilyResearchAdapter

    def broken_post(url, body, timeout):
        raise ConnectionError("simulated failure")

    adapter = TavilyResearchAdapter(api_key="fake-key", http_post=broken_post)
    brief = adapter.research("photosynthesis")
    assert brief.facts == []


# -- BraveSearchResearchAdapter (ADR-032) -------------------------------

def test_brave_unavailable_without_key():
    from backend.adapters.research.brave_research import BraveSearchResearchAdapter
    assert BraveSearchResearchAdapter(api_key="").is_available() is False


def test_brave_extracts_descriptions_and_strips_markup():
    from backend.adapters.research.brave_research import BraveSearchResearchAdapter

    class FakeClient:
        def get(self, url, headers=None, timeout=10):
            return {"status_code": 200, "json": {"web": {"results": [
                {"description": "It happens in <strong>chloroplasts</strong>.",
                 "url": "https://example.com/a"},
            ]}}}

    adapter = BraveSearchResearchAdapter(api_key="fake-key", http_client=FakeClient())
    brief = adapter.research("photosynthesis")
    assert brief.facts == ["It happens in chloroplasts."]
    assert brief.sources == ["https://example.com/a"]


def test_brave_never_raises_on_broken_client():
    from backend.adapters.research.brave_research import BraveSearchResearchAdapter

    class BrokenClient:
        def get(self, *a, **k):
            raise ConnectionError("simulated failure")

    adapter = BraveSearchResearchAdapter(api_key="fake-key", http_client=BrokenClient())
    brief = adapter.research("photosynthesis")
    assert brief.facts == []


# -- CompositeResearchAdapter (ADR-032: merges, doesn't just fail over) -

class FakeResearchProvider:
    def __init__(self, facts, sources=None, available=True):
        self._facts = facts
        self._sources = sources or []
        self._available = available
        self.call_count = 0

    def is_available(self):
        return self._available

    def research(self, topic):
        self.call_count += 1
        from backend.ports.ai_pipeline import ResearchBrief
        return ResearchBrief(facts=self._facts, sources=self._sources)


def test_composite_merges_facts_from_multiple_providers():
    from backend.adapters.research.composite_research import CompositeResearchAdapter
    p1 = FakeResearchProvider(facts=["fact one", "fact two"], sources=["url1"])
    p2 = FakeResearchProvider(facts=["fact three"], sources=["url2"])
    composite = CompositeResearchAdapter([p1, p2])
    brief = composite.research("topic")
    assert brief.facts == ["fact one", "fact two", "fact three"]
    assert brief.sources == ["url1", "url2"]
    assert p1.call_count == 1
    assert p2.call_count == 1


def test_composite_dedupes_facts_across_providers():
    from backend.adapters.research.composite_research import CompositeResearchAdapter
    p1 = FakeResearchProvider(facts=["Photosynthesis converts light to energy."])
    p2 = FakeResearchProvider(facts=["photosynthesis converts light to energy.",  # same, different case
                                       "A genuinely new fact."])
    composite = CompositeResearchAdapter([p1, p2])
    brief = composite.research("topic")
    assert len(brief.facts) == 2  # duplicate collapsed, new fact kept


def test_composite_skips_unavailable_providers():
    from backend.adapters.research.composite_research import CompositeResearchAdapter
    unavailable = FakeResearchProvider(facts=["should not appear"], available=False)
    available = FakeResearchProvider(facts=["should appear"])
    composite = CompositeResearchAdapter([unavailable, available])
    brief = composite.research("topic")
    assert brief.facts == ["should appear"]
    assert unavailable.call_count == 0


def test_composite_never_raises_when_a_provider_throws():
    from backend.adapters.research.composite_research import CompositeResearchAdapter

    class BrokenProvider:
        def is_available(self):
            return True

        def research(self, topic):
            raise ConnectionError("simulated failure")

    working = FakeResearchProvider(facts=["still works"])
    composite = CompositeResearchAdapter([BrokenProvider(), working])
    brief = composite.research("topic")
    assert brief.facts == ["still works"]


def test_composite_respects_max_total_facts_cap():
    from backend.adapters.research.composite_research import CompositeResearchAdapter, MAX_TOTAL_FACTS
    many_facts = [f"unique fact {i}" for i in range(20)]
    p1 = FakeResearchProvider(facts=many_facts)
    composite = CompositeResearchAdapter([p1])
    brief = composite.research("topic")
    assert len(brief.facts) <= MAX_TOTAL_FACTS


def test_composite_is_available_if_any_provider_available():
    from backend.adapters.research.composite_research import CompositeResearchAdapter
    composite = CompositeResearchAdapter([
        FakeResearchProvider(facts=[], available=False),
        FakeResearchProvider(facts=[], available=True),
    ])
    assert composite.is_available() is True


def test_composite_unavailable_when_no_provider_available():
    from backend.adapters.research.composite_research import CompositeResearchAdapter
    composite = CompositeResearchAdapter([FakeResearchProvider(facts=[], available=False)])
    assert composite.is_available() is False


def test_composite_returns_empty_brief_for_empty_topic():
    from backend.adapters.research.composite_research import CompositeResearchAdapter
    p1 = FakeResearchProvider(facts=["should not be called"])
    composite = CompositeResearchAdapter([p1])
    brief = composite.research("   ")
    assert brief.facts == []
    assert p1.call_count == 0


# -- registry wiring (ADR-032: research is on by default now) -----------

def test_registry_builds_composite_with_wikipedia_by_default(monkeypatch):
    # Opts out of the root conftest's autouse hermetic-default fixture
    # (which mocks get_research_adapter to always return
    # NullResearchAdapter) — this test's whole purpose is to verify
    # the REAL, unmocked registry wiring logic, not a mocked stand-in.
    monkeypatch.undo()
    from backend.adapters import registry
    for var in ("TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY", "OPENPRESENT_RESEARCH_ADAPTER",
                "OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH"):
        monkeypatch.delenv(var, raising=False)
    registry._research_adapter_instance = None
    adapter = registry.get_research_adapter()
    assert type(adapter).__name__ == "CompositeResearchAdapter"
    assert adapter.is_available() is True  # Wikipedia alone makes it available, no keys needed
    registry._research_adapter_instance = None


def test_registry_research_can_be_fully_disabled(monkeypatch):
    # Same opt-out — this test also exercises the real registry
    # function, this time its explicit-disable branch.
    monkeypatch.undo()
    from backend.adapters import registry
    monkeypatch.setenv("OPENPRESENT_RESEARCH_ADAPTER", "null")
    registry._research_adapter_instance = None
    adapter = registry.get_research_adapter()
    assert adapter.is_available() is False
    registry._research_adapter_instance = None
