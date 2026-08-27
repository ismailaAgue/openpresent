"""SQLite implementation of QuotaPort (ADR-043). Same pattern as
adapters/queue/sqlite_adapter.py — dev/local here, Postgres in prod,
identical logic on either side of the QuotaPort boundary."""

import sqlite3
import time
from backend.ports.quota import QuotaPort


class SqliteQuotaAdapter(QuotaPort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS quota_counters (
                key TEXT NOT NULL,
                window_start INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (key, window_start)
            )
        """)
        self._conn.commit()

    def record_attempt(self, key: str, window_seconds: int) -> int:
        window_start = int(time.time() // window_seconds) * window_seconds
        # Single atomic upsert — no read-then-write race between two
        # concurrent requests from the same key incrementing the same
        # window (the earlier ADR-042 fix was exactly this class of bug
        # elsewhere in this codebase; not repeating it here).
        self._conn.execute(
            """
            INSERT INTO quota_counters (key, window_start, count) VALUES (?, ?, 1)
            ON CONFLICT(key, window_start) DO UPDATE SET count = count + 1
            """,
            (key, window_start),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT count FROM quota_counters WHERE key = ? AND window_start = ?",
            (key, window_start),
        ).fetchone()
        return row[0]
