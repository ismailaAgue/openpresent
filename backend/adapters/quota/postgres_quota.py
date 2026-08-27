"""Postgres-backed Quota adapter — same QuotaPort contract as
SqliteQuotaAdapter, persists across web service restarts. Same
connection-pool pattern as postgres_queue.py (ADR-019 reasoning)."""

import time
from psycopg2 import pool as pg_pool
from backend.ports.quota import QuotaPort


class PostgresQuotaAdapter(QuotaPort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_quota_counters (
                        key TEXT NOT NULL,
                        window_start BIGINT NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (key, window_start)
                    )
                """)
        finally:
            self._pool.putconn(conn)

    def record_attempt(self, key: str, window_seconds: int) -> int:
        window_start = int(time.time() // window_seconds) * window_seconds
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                # ON CONFLICT ... DO UPDATE with RETURNING — single
                # round trip, atomic, no read-then-write race between
                # concurrent requests incrementing the same window.
                cur.execute(
                    """
                    INSERT INTO op_quota_counters (key, window_start, count)
                    VALUES (%s, %s, 1)
                    ON CONFLICT (key, window_start) DO UPDATE SET count = op_quota_counters.count + 1
                    RETURNING count
                    """,
                    (key, window_start),
                )
                return cur.fetchone()[0]
        finally:
            self._pool.putconn(conn)
