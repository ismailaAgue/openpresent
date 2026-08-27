"""Contract tests for QuotaPort / SqliteQuotaAdapter (ADR-043)."""

import time
from backend.adapters.quota.sqlite_adapter import SqliteQuotaAdapter


def make_quota():
    return SqliteQuotaAdapter(":memory:")


def test_first_attempt_returns_count_one():
    q = make_quota()
    assert q.record_attempt("user:1", window_seconds=86400) == 1


def test_repeated_attempts_increment():
    q = make_quota()
    q.record_attempt("user:1", window_seconds=86400)
    q.record_attempt("user:1", window_seconds=86400)
    assert q.record_attempt("user:1", window_seconds=86400) == 3


def test_different_keys_are_independent():
    q = make_quota()
    q.record_attempt("user:1", window_seconds=86400)
    q.record_attempt("user:1", window_seconds=86400)
    # A different key's count is entirely unaffected by user:1's usage —
    # this is the whole point (per-user/per-IP caps, not a shared pool).
    assert q.record_attempt("user:2", window_seconds=86400) == 1


def test_count_continues_past_a_hypothetical_limit():
    """The port's job is counting, not enforcing — record_attempt keeps
    incrementing past any limit a caller might apply. Policy (what to do
    once a count exceeds some limit) lives in the caller, not the port,
    per ports/quota.py's own docstring on this."""
    q = make_quota()
    counts = [q.record_attempt("user:1", window_seconds=86400) for _ in range(10)]
    assert counts == list(range(1, 11))


def test_new_window_resets_the_count():
    """A short window makes this observable without mocking time: wait
    past the window boundary and the count starts over at 1."""
    q = make_quota()
    q.record_attempt("user:1", window_seconds=1)
    q.record_attempt("user:1", window_seconds=1)
    time.sleep(1.1)
    assert q.record_attempt("user:1", window_seconds=1) == 1
