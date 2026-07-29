"""
Worker — Codebase Handbook Section 6, Phase 2.

Pulls jobs off the Queue Port, invokes the generation engine, writes
results back. This is what makes the API layer non-blocking: the API
only ever enqueues and reports status, never does the actual work.

Fault tolerance: on failure, fail() is called with retry=True, so a
transient error (e.g. a flaky AI call, though AI failures shouldn't
normally reach here since the AI Port already catches its own errors)
gets retried up to MAX_ATTEMPTS before landing in a terminal FAILED
state — the dead-letter gap flagged in the earlier scaling review.
"""

import base64
from backend.adapters import registry
from backend.engines.generate import generate_presentation


def process_one_job() -> bool:
    """Process a single pending job, if any. Returns True if a job was
    processed (regardless of success/failure), False if queue was empty."""
    queue = registry.get_queue_adapter()
    job = queue.dequeue()
    if job is None:
        return False

    try:
        file_bytes = base64.b64decode(job.payload["file_b64"])
        recipe, output_bytes = generate_presentation(
            file_bytes=file_bytes,
            filename=job.payload["filename"],
            export_format=job.payload.get("export_format", "pptx"),
            audience_type=job.payload.get("audience_type", "student_school"),
            language=job.payload.get("language", "en"),
        )

        project_id = None
        owner_id = job.payload.get("owner_id")
        if owner_id:
            # Logged-in user -> persist as a reusable project (recipe,
            # not the file — Constitution Principle 4). Anonymous use
            # stays fully supported without an account (Phase 3 keeps
            # the no-account-required promise for quick use).
            storage = registry.get_storage_adapter()
            title = recipe.outline.slides[0].title if recipe.outline.slides else "Untitled"
            project_id = storage.save_recipe(owner_id, recipe, title)

        queue.complete(job.id, {
            "structure_source": recipe.outline.structure_source.value,
            "slide_count": len(recipe.outline.slides),
            "file_b64": base64.b64encode(output_bytes).decode("ascii"),
            "export_format": job.payload.get("export_format", "pptx"),
            "project_id": project_id,
        })
        registry.get_analytics_adapter().record_generation(
            owner_id, recipe.outline.structure_source.value
        )
    except Exception as e:
        queue.fail(job.id, str(e), retry=True)

    return True


def run_worker_loop(max_jobs: int | None = None, poll_interval: float = 0.5):
    """Simple synchronous worker loop for Phase 2. A production
    deployment (Blueprint Stage 2+) would run several of these as
    separate processes, sized to queue depth per the Deployment
    Strategy — the loop body itself doesn't change."""
    import time
    processed = 0
    while max_jobs is None or processed < max_jobs:
        did_work = process_one_job()
        processed += 1 if did_work else 0
        if not did_work:
            if max_jobs is not None:
                break
            time.sleep(poll_interval)
