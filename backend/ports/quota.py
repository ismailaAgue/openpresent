"""
Quota Port — ADR-043 (cost circuit breaker).

Responsibility: a fixed-window request counter used to cap how many
generations a single caller can trigger per window, so a single
generation firing 6+ AI calls (Strategy/Outline/Content/Layout/Review/
research — see the pipeline docstrings) can't run up unbounded spend
across many requests. This was flagged as the #1 real risk in the
original project handoff doc, before any of this existed: "A single
generation can now trigger 6+ AI calls... Nothing caps spend."

Deliberately NOT a general-purpose rate limiter (no per-IP request
throttling, no burst/leaky-bucket logic) — just a counter, because a
counter is all a cost cap needs, and every extra mechanism here is
extra surface for a solo founder to maintain for no real benefit at
current scale. If abuse-focused rate limiting (the "no API rate
limiting / abuse protection" item in the handoff doc's infra gaps)
becomes a real need later, that's a genuinely separate concern from
"cap what this could cost me" and deserves its own port rather than
overloading this one.
"""

from typing import Protocol


class QuotaPort(Protocol):
    def record_attempt(self, key: str, window_seconds: int) -> int:
        """Atomically increments the counter for `key` within the
        current fixed window (bucketed by window_seconds, e.g. a
        86400-second window buckets by UTC calendar day) and returns
        the new count for that window. Always increments — including
        the call that pushes the count over a caller's limit — so the
        count is exactly "how many attempts landed here", not
        "how many attempts we chose to allow"; callers compare the
        returned count against their own limit to decide whether to
        proceed. This keeps the port's job to counting, not policy."""
        ...
