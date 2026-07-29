import pytest
from backend.adapters.analytics.sqlite_analytics import SqliteAnalyticsAdapter


def test_records_and_counts_generations():
    a = SqliteAnalyticsAdapter(":memory:")
    a.record_generation("user1", "rule-based")
    a.record_generation("user1", "rule-based")
    a.record_generation(None, "rule-based")  # anonymous
    summary = a.get_retention_summary()
    assert summary.total_generations == 3
    assert summary.unique_users == 1  # anonymous doesn't count toward unique


def test_same_day_repeat_is_not_returning():
    a = SqliteAnalyticsAdapter(":memory:")
    a.record_generation("user1", "rule-based")
    a.record_generation("user1", "rule-based")  # same day, different generation
    summary = a.get_retention_summary()
    assert summary.returning_users == 0  # same-day repeats don't count as retention


def test_different_day_repeat_counts_as_returning(monkeypatch):
    a = SqliteAnalyticsAdapter(":memory:")
    import backend.adapters.analytics.sqlite_analytics as mod

    # Simulate two generations on different days by inserting directly
    # with distinct day_bucket values, since real "come back next
    # assignment" behavior spans days/weeks in practice.
    a._conn.execute(
        "INSERT INTO events (event_type, owner_id, structure_source, occurred_at, day_bucket) "
        "VALUES ('generation', 'user1', 'rule-based', 1000, '2026-01-01')"
    )
    a._conn.execute(
        "INSERT INTO events (event_type, owner_id, structure_source, occurred_at, day_bucket) "
        "VALUES ('generation', 'user1', 'rule-based', 2000, '2026-01-15')"
    )
    a._conn.commit()
    summary = a.get_retention_summary()
    assert summary.returning_users == 1


def test_records_exports_separately_from_generations():
    a = SqliteAnalyticsAdapter(":memory:")
    a.record_generation("user1", "rule-based")
    a.record_export("user1")
    a.record_export("user1")
    summary = a.get_retention_summary()
    assert summary.exports_completed == 2
    assert summary.total_generations == 1
