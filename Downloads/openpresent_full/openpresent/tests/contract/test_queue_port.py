import pytest
from backend.adapters.queue.sqlite_adapter import SqliteQueueAdapter
from backend.ports.queue import JobStatus


def make_queue():
    return SqliteQueueAdapter(":memory:")


def test_enqueue_then_dequeue():
    q = make_queue()
    job_id = q.enqueue("generate", {"filename": "essay.txt"})
    job = q.dequeue()
    assert job.id == job_id
    assert job.status == JobStatus.RUNNING
    assert job.payload == {"filename": "essay.txt"}


def test_dequeue_empty_queue_returns_none():
    q = make_queue()
    assert q.dequeue() is None


def test_complete_sets_result_and_status():
    q = make_queue()
    job_id = q.enqueue("generate", {})
    q.dequeue()
    q.complete(job_id, {"file_size": 1234})
    job = q.get_status(job_id)
    assert job.status == JobStatus.DONE
    assert job.result == {"file_size": 1234}


def test_fail_with_retry_returns_to_pending():
    q = make_queue()
    job_id = q.enqueue("generate", {})
    q.dequeue()  # attempts = 1
    q.fail(job_id, "temporary error", retry=True)
    job = q.get_status(job_id)
    assert job.status == JobStatus.PENDING
    assert job.error == "temporary error"


def test_fail_without_retry_goes_to_dead_letter():
    q = make_queue()
    job_id = q.enqueue("generate", {})
    q.dequeue()
    q.fail(job_id, "permanent error", retry=False)
    job = q.get_status(job_id)
    assert job.status == JobStatus.FAILED


def test_exceeding_max_attempts_goes_to_dead_letter_even_with_retry_true():
    q = make_queue()
    job_id = q.enqueue("generate", {})
    for _ in range(5):  # exceeds MAX_ATTEMPTS
        q.dequeue()
        q.fail(job_id, "still failing", retry=True)
    job = q.get_status(job_id)
    assert job.status == JobStatus.FAILED  # never retries forever


def test_depth_reflects_pending_count():
    q = make_queue()
    assert q.depth() == 0
    q.enqueue("generate", {})
    q.enqueue("generate", {})
    assert q.depth() == 2
    q.dequeue()
    assert q.depth() == 1  # one moved to RUNNING, no longer PENDING
