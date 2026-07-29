"""
SQLite-backed Analytics adapter. Same swap story as every other
adapter — points at a real analytics service later without touching
anything that calls this port.
"""

import sqlite3
import time
from backend.ports.analytics import AnalyticsPort, RetentionSummary


class SqliteAnalyticsAdapter(AnalyticsPort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                owner_id TEXT,
                structure_source TEXT,
                occurred_at REAL NOT NULL,
                day_bucket TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def record_generation(self, owner_id: str | None, structure_source: str) -> None:
        now = time.time()
        self._conn.execute(
            "INSERT INTO events (event_type, owner_id, structure_source, occurred_at, day_bucket) "
            "VALUES ('generation', ?, ?, ?, ?)",
            (owner_id, structure_source, now, _day_bucket(now)),
        )
        self._conn.commit()

    def record_export(self, owner_id: str | None) -> None:
        now = time.time()
        self._conn.execute(
            "INSERT INTO events (event_type, owner_id, occurred_at, day_bucket) "
            "VALUES ('export', ?, ?, ?)",
            (owner_id, now, _day_bucket(now)),
        )
        self._conn.commit()

    def get_retention_summary(self) -> RetentionSummary:
        total = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = 'generation'"
        ).fetchone()[0]

        exports = self._conn.execute(
            "SELECT COUNT(*) FROM events WHERE event_type = 'export'"
        ).fetchone()[0]

        unique = self._conn.execute(
            "SELECT COUNT(DISTINCT owner_id) FROM events "
            "WHERE event_type = 'generation' AND owner_id IS NOT NULL"
        ).fetchone()[0]

        # Returning = generated on 2+ distinct days. This is the actual
        # retention signal — same-day repeat generation doesn't count,
        # since the real question is "did they come back for the NEXT
        # assignment," per the retention discussion.
        returning = self._conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT owner_id FROM events
                WHERE event_type = 'generation' AND owner_id IS NOT NULL
                GROUP BY owner_id
                HAVING COUNT(DISTINCT day_bucket) >= 2
            )
        """).fetchone()[0]

        return RetentionSummary(
            total_generations=total, unique_users=unique,
            returning_users=returning, exports_completed=exports,
        )


def _day_bucket(timestamp: float) -> str:
    import datetime
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y-%m-%d")
