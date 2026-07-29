"""
Postgres-backed Queue adapter — same QueuePort contract as
SqliteQueueAdapter, persists across web service restarts.
"""

import json
import time
import uuid
from typing import Any
from backend.ports.queue import QueuePort, Job, JobStatus

MAX_ATTEMPTS = 3


class PostgresQueueAdapter(QueuePort):
    def __init__(self, database_url: str):
        import psycopg2
        self._conn = psycopg2.connect(database_url)
        self._conn.autocommit = True
        self._ensure_schema()
        self._conn.autocommit = False  # dequeue needs a real transaction for FOR UPDATE SKIP LOCKED to mean anything

    def _ensure_schema(self):
        with self._conn.cursor() as cur:
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

    def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO op_jobs (id, job_type, payload, status, attempts, created_at) "
                "VALUES (%s, %s, %s, %s, 0, %s)",
                (job_id, job_type, json.dumps(payload), JobStatus.PENDING.value, time.time()),
            )
        self._conn.commit()
        return job_id

    def dequeue(self) -> Job | None:
        # Explicit transaction: the SELECT ... FOR UPDATE SKIP LOCKED
        # lock must stay held until the UPDATE that follows commits,
        # or it provides no real protection against two workers
        # grabbing the same job (Stage 2+ concern — harmless but inert
        # under the current single-in-process-worker Stage 0-1 setup).
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT id FROM op_jobs WHERE status = %s
                ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED
            """, (JobStatus.PENDING.value,))
            row = cur.fetchone()
            if row is None:
                self._conn.rollback()
                return None
            job_id = row[0]
            cur.execute(
                "UPDATE op_jobs SET status = %s, attempts = attempts + 1 WHERE id = %s",
                (JobStatus.RUNNING.value, job_id),
            )
        self._conn.commit()
        return self.get_status(job_id)

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE op_jobs SET status = %s, result = %s WHERE id = %s",
                (JobStatus.DONE.value, json.dumps(result), job_id),
            )
        self._conn.commit()

    def fail(self, job_id: str, error: str, retry: bool = True) -> None:
        with self._conn.cursor() as cur:
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
        self._conn.commit()

    def get_status(self, job_id: str) -> Job | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, job_type, payload, status, result, error, attempts "
                "FROM op_jobs WHERE id = %s",
                (job_id,),
            )
            row = cur.fetchone()
        self._conn.commit()  # close the implicit read transaction cleanly
        if row is None:
            return None
        return Job(
            id=row[0], job_type=row[1], payload=json.loads(row[2]),
            status=JobStatus(row[3]), result=json.loads(row[4]) if row[4] else None,
            error=row[5], attempts=row[6],
        )

    def depth(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM op_jobs WHERE status = %s", (JobStatus.PENDING.value,))
            result = cur.fetchone()[0]
        self._conn.commit()
        return result
