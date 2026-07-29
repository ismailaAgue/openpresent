"""
DB-backed Queue adapter — Technical Blueprint Section 12, Stage 0-1.

Uses SQLite for local/dev purposes here (this sandbox has no Postgres
server available). Production per ADR-006 targets managed Postgres;
because this adapter only speaks through the QueuePort interface,
pointing it at Postgres instead is a connection-string change, not a
logic change — nothing in engines/ or api/ needs to know the difference.
"""

import json
import sqlite3
import time
import uuid
from typing import Any
from backend.ports.queue import QueuePort, Job, JobStatus

MAX_ATTEMPTS = 3


class SqliteQueueAdapter(QueuePort):
    def __init__(self, db_path: str = ":memory:"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                attempts INTEGER DEFAULT 0,
                created_at REAL NOT NULL
            )
        """)
        self._conn.commit()

    def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO jobs (id, job_type, payload, status, attempts, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (job_id, job_type, json.dumps(payload), JobStatus.PENDING.value, time.time()),
        )
        self._conn.commit()
        return job_id

    def dequeue(self) -> Job | None:
        cur = self._conn.execute(
            "SELECT id FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT 1",
            (JobStatus.PENDING.value,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        job_id = row[0]
        self._conn.execute(
            "UPDATE jobs SET status = ?, attempts = attempts + 1 WHERE id = ?",
            (JobStatus.RUNNING.value, job_id),
        )
        self._conn.commit()
        return self.get_status(job_id)

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        self._conn.execute(
            "UPDATE jobs SET status = ?, result = ? WHERE id = ?",
            (JobStatus.DONE.value, json.dumps(result), job_id),
        )
        self._conn.commit()

    def fail(self, job_id: str, error: str, retry: bool = True) -> None:
        row = self._conn.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()
        attempts = row[0] if row else MAX_ATTEMPTS
        if retry and attempts < MAX_ATTEMPTS:
            # Dead-letter policy: retry by returning to PENDING, per the
            # failure-path gap flagged in the earlier scaling review.
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ? WHERE id = ?",
                (JobStatus.PENDING.value, error, job_id),
            )
        else:
            self._conn.execute(
                "UPDATE jobs SET status = ?, error = ? WHERE id = ?",
                (JobStatus.FAILED.value, error, job_id),
            )
        self._conn.commit()

    def get_status(self, job_id: str) -> Job | None:
        row = self._conn.execute(
            "SELECT id, job_type, payload, status, result, error, attempts FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        return Job(
            id=row[0], job_type=row[1], payload=json.loads(row[2]),
            status=JobStatus(row[3]), result=json.loads(row[4]) if row[4] else None,
            error=row[5], attempts=row[6],
        )

    def depth(self) -> int:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = ?", (JobStatus.PENDING.value,)
        )
        return cur.fetchone()[0]
