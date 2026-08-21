"""
Postgres-backed Queue adapter — same QueuePort contract as
SqliteQueueAdapter, persists across web service restarts.

Revision (ADR-019): uses a connection pool instead of one shared
connection (see postgres_auth.py for the full reasoning). dequeue()
still needs a real transaction (autocommit off) for FOR UPDATE SKIP
LOCKED to actually protect against two workers grabbing the same job —
the connection's autocommit is explicitly toggled off for that one
operation and reset to on before the connection returns to the pool,
so every other method can assume a clean, simple autocommit connection.
"""

import json
import time
import uuid
from typing import Any
from psycopg2 import pool as pg_pool
from backend.ports.queue import QueuePort, Job, JobStatus

MAX_ATTEMPTS = 3


class PostgresQueueAdapter(QueuePort):
    def __init__(self, database_url: str):
        self._pool = pg_pool.ThreadedConnectionPool(1, 5, database_url)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS op_jobs (
                        id TEXT PRIMARY KEY,
                        job_type TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result TEXT,
                        error TEXT,
                        attempts INTEGER DEFAULT 0,
                        created_at DOUBLE PRECISION NOT NULL
                    )
                """)
                # ADR-040 — additive column, safe on a pre-existing prod table.
                cur.execute("ALTER TABLE op_jobs ADD COLUMN IF NOT EXISTS stage TEXT")
        finally:
            self._pool.putconn(conn)

    def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO op_jobs (id, job_type, payload, status, attempts, created_at) "
                    "VALUES (%s, %s, %s, %s, 0, %s)",
                    (job_id, job_type, json.dumps(payload), JobStatus.PENDING.value, time.time()),
                )
            return job_id
        finally:
            self._pool.putconn(conn)

    def dequeue(self) -> Job | None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = False  # real transaction needed for FOR UPDATE SKIP LOCKED to mean anything
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id FROM op_jobs WHERE status = %s
                        ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED
                    """, (JobStatus.PENDING.value,))
                    row = cur.fetchone()
                    if row is None:
                        conn.rollback()
                        return None
                    job_id = row[0]
                    cur.execute(
                        "UPDATE op_jobs SET status = %s, attempts = attempts + 1 WHERE id = %s",
                        (JobStatus.RUNNING.value, job_id),
                    )
                conn.commit()
            finally:
                conn.autocommit = True  # restore clean state before returning to the pool
        finally:
            self._pool.putconn(conn)
        return self.get_status(job_id)

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE op_jobs SET status = %s, result = %s WHERE id = %s",
                    (JobStatus.DONE.value, json.dumps(result), job_id),
                )
        finally:
            self._pool.putconn(conn)

    def fail(self, job_id: str, error: str, retry: bool = True) -> None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT attempts FROM op_jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
                attempts = row[0] if row else MAX_ATTEMPTS
                if retry and attempts < MAX_ATTEMPTS:
                    cur.execute(
                        "UPDATE op_jobs SET status = %s, error = %s WHERE id = %s",
                        (JobStatus.PENDING.value, error, job_id),
                    )
                else:
                    cur.execute(
                        "UPDATE op_jobs SET status = %s, error = %s WHERE id = %s",
                        (JobStatus.FAILED.value, error, job_id),
                    )
        finally:
            self._pool.putconn(conn)

    def get_status(self, job_id: str) -> Job | None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, job_type, payload, status, result, error, attempts, stage "
                    "FROM op_jobs WHERE id = %s",
                    (job_id,),
                )
                row = cur.fetchone()
        finally:
            self._pool.putconn(conn)
        if row is None:
            return None
        return Job(
            id=row[0], job_type=row[1], payload=json.loads(row[2]),
            status=JobStatus(row[3]), result=json.loads(row[4]) if row[4] else None,
            error=row[5], attempts=row[6], stage=row[7],
        )

    def update_stage(self, job_id: str, stage: str) -> None:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("UPDATE op_jobs SET stage = %s WHERE id = %s", (stage, job_id))
        except Exception:
            pass  # best-effort — never let a progress update break generation
        finally:
            self._pool.putconn(conn)

    def depth(self) -> int:
        conn = self._pool.getconn()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM op_jobs WHERE status = %s", (JobStatus.PENDING.value,))
                result = cur.fetchone()[0]
        finally:
            self._pool.putconn(conn)
        return result
