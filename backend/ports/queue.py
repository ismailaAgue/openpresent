"""
Queue Port — Technical Blueprint Section 3.8.

Buffer between incoming jobs and available worker capacity. Everything
else in the system only ever calls enqueue()/dequeue()/status() —
swapping the backing implementation (DB-backed table -> managed queue
service, per the staged deployment plan) is invisible to callers.
"""

from typing import Protocol, Any
from enum import Enum
from dataclasses import dataclass


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    job_type: str
    payload: dict[str, Any]
    status: JobStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    stage: str | None = None
    """Coarse-grained progress label set by the engine mid-run (ADR-040),
    e.g. "building_outline" — best-effort, informational only. None
    while PENDING, and not guaranteed fresh for every job_type (only
    generate_presentation_from_topic reports it as of ADR-040)."""


class QueuePort(Protocol):
    def enqueue(self, job_type: str, payload: dict[str, Any]) -> str:
        """Add a job to the queue, return its job id."""
        ...

    def dequeue(self) -> Job | None:
        """Pull the next pending job for a worker to process, marking it
        RUNNING. Returns None if the queue is empty."""
        ...

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        ...

    def fail(self, job_id: str, error: str, retry: bool = True) -> None:
        """Mark a job failed. If retry is True and attempts remain,
        the job returns to PENDING (retry policy, per the scaling
        review's failure-path requirement) — otherwise DEAD (FAILED,
        terminal)."""
        ...

    def get_status(self, job_id: str) -> Job | None:
        ...

    def update_stage(self, job_id: str, stage: str) -> None:
        """Best-effort progress update while a job is RUNNING (ADR-040).
        Must never raise on an unknown/already-terminal job_id — this is
        called from deep inside the generation engine and a stage-update
        failure must not abort or corrupt the actual generation."""
        ...

    def depth(self) -> int:
        """Number of PENDING jobs — the core health metric (Blueprint
        Section on monitoring; ADR-012 cost governance)."""
        ...
