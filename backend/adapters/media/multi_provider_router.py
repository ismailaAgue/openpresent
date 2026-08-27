"""
MultiProviderMediaAdapter — ADR-029.

The MediaPort implementation actually wired up by the registry now.
Replaces "call one provider, take its first result" with:

  1. Check the in-process candidate-metadata cache for this query
     (relevance.CandidateCache) — skip provider calls entirely on a
     cache hit within the TTL.
  2. On a miss, query each configured provider IN ORDER (a provider
     is skipped if unconfigured or over its self-tracked hourly
     quota — QuotaTracker) until at least MIN_CANDIDATES_TO_STOP
     candidates are collected, or providers are exhausted. This is
     the "fallback providers" requirement (spec Section 8) — a
     provider being down/exhausted degrades to the next one, not to
     "no image."
  3. Score every candidate against the query (relevance.score_relevance)
     and sort descending.
  4. Walk the sorted list, skipping any candidate whose image_id is in
     exclude_ids (duplicate prevention within one deck), and fetch
     bytes for the first one that isn't excluded.
  5. Cache the scored candidate metadata (not bytes) for next time.

Default provider order: Unsplash, Pexels, Pixabay, Wikimedia — cheapest
proportional to the product's existing Unsplash investment first,
Wikimedia (no key required, always configured) last as the universal
fallback.
"""

from backend.ports.media import MediaPort
from backend.models.media import ImageResult
from backend.adapters.media.relevance import score_relevance, CandidateCache
from backend.adapters.media.provider_base import Candidate
from backend.monitoring.sentry_setup import capture_exception

MIN_CANDIDATES_TO_STOP = 5
PER_PROVIDER_PAGE_SIZE = 5


class MultiProviderMediaAdapter(MediaPort):
    def __init__(self, providers: list, cache: CandidateCache | None = None):
        # providers: ordered list of ImageProviderAdapter-shaped objects
        # (duck-typed — see provider_base.ImageProviderAdapter). Order
        # is priority order; unconfigured/quota-exhausted ones are
        # skipped automatically via is_available().
        self.providers = providers
        self._cache = cache or CandidateCache()

    def is_available(self) -> bool:
        return any(p.is_available() for p in self.providers)

    def search_image(self, query: str, exclude_ids: set[str] | None = None) -> ImageResult | None:
        if not query:
            return None
        exclude_ids = exclude_ids or set()

        candidates = self._cache.get(query)
        if candidates is None:
            candidates = self._discover_candidates(query)
            self._cache.set(query, candidates)

        scored = sorted(candidates, key=lambda c: c["score"], reverse=True)
        for c in scored:
            if c["image_id"] in exclude_ids:
                continue
            provider = self._provider_by_name(c["provider"])
            if provider is None:
                continue
            candidate_obj = Candidate(
                image_id=c["image_id"], provider=c["provider"], fetch_url=c["fetch_url"],
                metadata_text=c["metadata_text"], attribution=c["attribution"],
            )
            try:
                image_bytes = provider.fetch_bytes(candidate_obj)
            except Exception:
                image_bytes = None
            if not image_bytes:
                continue  # dead link or fetch failure — try the next-best candidate
            return ImageResult(
                image_bytes=image_bytes, image_id=c["image_id"], provider=c["provider"],
                relevance_score=c["score"], attribution=c["attribution"],
            )
        return None  # every candidate excluded or unfetchable — no image, deck still renders fine

    # -- internals -------------------------------------------------------

    def _discover_candidates(self, query: str) -> list[dict]:
        collected: list[dict] = []
        for provider in self.providers:
            try:
                if not provider.is_available():
                    continue
                found = provider.search_candidates(query, per_page=PER_PROVIDER_PAGE_SIZE)
            except Exception as e:
                capture_exception(e, tags={"stage": "image_provider", "provider": getattr(provider, "name", "?")})
                found = []
            for c in found:
                collected.append({
                    "image_id": c.image_id, "provider": c.provider, "fetch_url": c.fetch_url,
                    "metadata_text": c.metadata_text, "attribution": c.attribution,
                    "score": score_relevance(query, c.metadata_text),
                })
            if len(collected) >= MIN_CANDIDATES_TO_STOP:
                break
        return collected

    def _provider_by_name(self, name: str):
        for p in self.providers:
            if p.name == name:
                return p
        return None
