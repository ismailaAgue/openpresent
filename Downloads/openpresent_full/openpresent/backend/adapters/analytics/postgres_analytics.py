"""
Postgres-backed Analytics adapter — same AnalyticsPort contract as
SqliteAnalyticsAdapter, persists across web service restarts.

Revision (ADR-019): uses a connection pool instead of one shared
connection — see postgres_auth.py's module docstring for the full
reasoning.
"""

import time
import datetime
from psycopg2 import pool as pg_pool
from backend.ports.analytics import AnalyticsPort, RetentionSummary


class PostgresAnalyticsAdapter(AnalyticsPort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_events (
                        id SERIAL PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        owner_id TEXT,
                        structure_source TEXT,
                        occurred_at DOUBLE PRECISION NOT NULL,
                        day_bucket TEXT NOT NULL
                    )
                """)
        finally:
            self._pool.putconn(conn)

    def record_generation(self, owner_id: str | None, structure_source: str) -> None:
        now = time.time()
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO op_events (event_type, owner_id, structure_source, occurred_at, day_bucket) "
                    "VALUES ('generation', %s, %s, %s, %s)",
                    (owner_id, structure_source, now, _day_bucket(now)),
                )
        finally:
            self._pool.putconn(conn)

    def record_export(self, owner_id: str | None) -> None:
        now = time.time()
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO op_events (event_type, owner_id, occurred_at, day_bucket) "
                    "VALUES ('export', %s, %s, %s)",
                    (owner_id, now, _day_bucket(now)),
                )
        finally:
            self._pool.putconn(conn)

    def get_retention_summary(self) -> RetentionSummary:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM op_events WHERE event_type = 'generation'")
                total = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM op_events WHERE event_type = 'export'")
                exports = cur.fetchone()[0]

                cur.execute(
                    "SELECT COUNT(DISTINCT owner_id) FROM op_events "
                    "WHERE event_type = 'generation' AND owner_id IS NOT NULL"
                )
                unique = cur.fetchone()[0]

                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT owner_id FROM op_events
                        WHERE event_type = 'generation' AND owner_id IS NOT NULL
                        GROUP BY owner_id
                        HAVING COUNT(DISTINCT day_bucket) >= 2
                    ) sub
                """)
                returning = cur.fetchone()[0]
        finally:
            self._pool.putconn(conn)

        return RetentionSummary(
            total_generations=total, unique_users=unique,
            returning_users=returning, exports_completed=exports,
        )


def _day_bucket(timestamp: float) -> str:
    return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y-%m-%d")
