from backend.adapters.media.relevance import score_relevance, CandidateCache
from backend.adapters.media.quota import QuotaTracker
from backend.adapters.media.multi_provider_router import MultiProviderMediaAdapter
from backend.adapters.media.provider_base import Candidate


def test_relevance_scores_higher_overlap_higher():
    high = score_relevance("mountain sunset", "a beautiful mountain sunset over the valley")
    low = score_relevance("mountain sunset", "a cat sleeping on a couch")
    assert high > low


def test_relevance_zero_for_no_metadata():
    assert score_relevance("mountains", "") == 0.0


def test_quota_tracker_allows_up_to_limit():
    q = QuotaTracker(limit_per_hour=2)
    assert q.has_quota() is True
    q.record_request()
    assert q.has_quota() is True
    q.record_request()
    assert q.has_quota() is False


def test_candidate_cache_roundtrip():
    cache = CandidateCache()
    assert cache.get("mountains") is None
    cache.set("mountains", [{"image_id": "x:1"}])
    assert cache.get("mountains") == [{"image_id": "x:1"}]


def test_candidate_cache_normalizes_query_casing_and_whitespace():
    cache = CandidateCache()
    cache.set("  Mountain   Sunset  ", [{"image_id": "x:1"}])
    assert cache.get("mountain sunset") == [{"image_id": "x:1"}]


class FakeProvider:
    def __init__(self, name, candidates, bytes_by_id=None, available=True):
        self.name = name
        self.requests_per_hour_limit = 1000
        self._candidates = candidates
        self._bytes_by_id = bytes_by_id or {}
        self._available = available
        self.search_calls = 0

    def is_available(self):
        return self._available

    def search_candidates(self, query, per_page=5):
        self.search_calls += 1
        return self._candidates

    def fetch_bytes(self, candidate):
        return self._bytes_by_id.get(candidate.image_id)


def test_router_picks_highest_scoring_candidate():
    candidates = [
        Candidate(image_id="p:low", provider="p", fetch_url="u1", metadata_text="cat sleeping"),
        Candidate(image_id="p:high", provider="p", fetch_url="u2", metadata_text="mountain sunset valley"),
    ]
    provider = FakeProvider("p", candidates, bytes_by_id={"p:high": b"HIGH", "p:low": b"LOW"})
    router = MultiProviderMediaAdapter(providers=[provider])
    result = router.search_image("mountain sunset")
    assert result.image_id == "p:high"
    assert result.image_bytes == b"HIGH"


def test_router_dedup_skips_excluded_id():
    candidates = [
        Candidate(image_id="p:high", provider="p", fetch_url="u2", metadata_text="mountain sunset valley"),
        Candidate(image_id="p:low", provider="p", fetch_url="u1", metadata_text="mountain view"),
    ]
    provider = FakeProvider("p", candidates, bytes_by_id={"p:high": b"HIGH", "p:low": b"LOW"})
    router = MultiProviderMediaAdapter(providers=[provider])
    result = router.search_image("mountain sunset", exclude_ids={"p:high"})
    assert result.image_id == "p:low"


def test_router_falls_back_to_next_provider_when_first_unavailable():
    p1 = FakeProvider("p1", [], available=False)
    p2 = FakeProvider("p2", [Candidate(image_id="p2:1", provider="p2", fetch_url="u",
                                         metadata_text="mountains")],
                       bytes_by_id={"p2:1": b"FROM_P2"})
    router = MultiProviderMediaAdapter(providers=[p1, p2])
    result = router.search_image("mountains")
    assert result.provider == "p2"
    assert result.image_bytes == b"FROM_P2"


def test_router_returns_none_when_no_provider_available():
    p1 = FakeProvider("p1", [], available=False)
    router = MultiProviderMediaAdapter(providers=[p1])
    assert router.search_image("mountains") is None


def test_router_caches_candidate_discovery_across_calls():
    candidates = [Candidate(image_id="p:1", provider="p", fetch_url="u", metadata_text="mountains")]
    provider = FakeProvider("p", candidates, bytes_by_id={"p:1": b"X"})
    router = MultiProviderMediaAdapter(providers=[provider])
    router.search_image("mountains")
    router.search_image("mountains", exclude_ids={"p:1"})  # second call, same query
    assert provider.search_calls == 1  # cache hit on the second call — no repeat discovery


def test_router_never_raises_when_a_provider_throws():
    class BrokenProvider:
        name = "broken"
        requests_per_hour_limit = 100

        def is_available(self):
            return True

        def search_candidates(self, query, per_page=5):
            raise ConnectionError("simulated failure")

        def fetch_bytes(self, candidate):
            raise ConnectionError("simulated failure")

    router = MultiProviderMediaAdapter(providers=[BrokenProvider()])
    assert router.search_image("mountains") is None
