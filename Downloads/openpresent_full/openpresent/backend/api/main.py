"""
Phase 1 API — synchronous, no queue yet (Phase 2 adds async processing).
Proves the core thesis end-to-end: upload -> real, downloadable deck.

Phase 2 additions: /generate/async (enqueue) + /jobs/{id} (poll status/result),
via the Queue Port + worker, per the roadmap's "real async processing."
The original synchronous /generate endpoint is kept for quick local testing.

Deployment note (see ADR-015): at Stage 0-1 (Blueprint Section 12), the
worker runs as a background thread inside this same process rather than
as a separate service. This matches the Blueprint's own staged plan
("single cheap VPS ... for the API" at Stage 0-1) and avoids a real-world
constraint discovered during deployment: Render's free tier only covers
one web service, not a separate background worker (that now requires a
paid plan). Splitting into a genuinely separate worker process happens
at Stage 2+, when queue depth actually justifies it — the QueuePort
abstraction means that split is a deployment change, not a code change.
"""

import base64
import os
import threading
import time
from backend.adapters import registry
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.engines.generate import generate_presentation
from backend.ports.ingestion import UnsupportedFileTypeError, CorruptFileError
from backend.ports.export import UnsupportedFormatError
from backend.ports.queue import JobStatus
from backend.ports.auth import EmailAlreadyRegisteredError, InvalidCredentialsError

app = FastAPI(title="OpenPresent API — Phase 3")

# CORS: the frontend (Vercel) and backend (Render) live on different
# domains, so the browser blocks requests between them unless the
# backend explicitly allows it — without this, every request from the
# deployed frontend fails with "Failed to fetch" and no further detail,
# even though the backend itself is working perfectly (curl/same-origin
# testing never surfaces this, which is why it wasn't caught earlier).
# allow_origins="*" is safe here: auth uses a manually-attached Bearer
# token (api-client.ts), not cookies, so there's no credential-based
# CORS risk from allowing any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_MEDIA_TYPES = {"pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


def _in_process_worker_loop():
    """Runs in a background thread inside the API process. See module
    docstring / ADR-015 for why this replaces a separate worker service
    at Stage 0-1. Controlled by OPENPRESENT_INPROCESS_WORKER (default
    "true") so it can be turned off once a real separate worker exists
    (Stage 2+) without touching this code — just an env var flip."""
    from backend.workers.generation_worker import process_one_job
    while True:
        try:
            did_work = process_one_job()
        except Exception:
            did_work = False  # never let a bad job crash the whole loop/thread
        time.sleep(0.5 if not did_work else 0)


@app.on_event("startup")
def _start_inprocess_worker():
    if os.environ.get("OPENPRESENT_INPROCESS_WORKER", "true").lower() == "true":
        thread = threading.Thread(target=_in_process_worker_loop, daemon=True)
        thread.start()


def _current_user(authorization: str | None):
    """Resolve the logged-in user from a 'Bearer <token>' header.
    Returns None if not authenticated — endpoints that require auth
    raise 401 themselves; endpoints where auth is optional (Phase 3
    doesn't require login to use the sync /generate endpoint, keeping
    the no-account-required promise intact for quick use) just get None."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):]
    return registry.get_auth_adapter().get_user_from_session(token)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/health")
def health():
    ai = registry.get_ai_adapter()
    queue = registry.get_queue_adapter()
    auth = registry.get_auth_adapter()
    storage = registry.get_storage_adapter()
    return {
        "status": "ok",
        "phase": 3,
        "ai_adapter": type(ai).__name__,
        "ai_available": ai.is_available(),
        "queue_depth": queue.depth(),
        # Diagnostic fields (ADR-018 verification): confirms whether
        # DATABASE_URL is actually being picked up server-side, rather
        # than inferring it indirectly through login behavior.
        "auth_adapter": type(auth).__name__,
        "storage_adapter": type(storage).__name__,
        "database_url_present": bool(registry._database_url()),
    }


# -- Auth ---------------------------------------------------------------

@app.post("/auth/register")
def register(req: RegisterRequest):
    try:
        user = registry.get_auth_adapter().register(req.email, req.password)
    except EmailAlreadyRegisteredError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"user_id": user.id, "email": user.email}


@app.post("/auth/login")
def login(req: LoginRequest):
    try:
        token = registry.get_auth_adapter().login(req.email, req.password)
    except InvalidCredentialsError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"session_token": token}


# -- Generation (sync — no account required, keeps quick-use free) -----

@app.post("/generate")
async def generate(file: UploadFile = File(...), export_format: str = "pptx"):
    file_bytes = await file.read()
    try:
        recipe, output_bytes = generate_presentation(
            file_bytes=file_bytes,
            filename=file.filename or "upload.txt",
            export_format=export_format,
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CorruptFileError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    registry.get_analytics_adapter().record_generation(None, recipe.outline.structure_source.value)
    registry.get_analytics_adapter().record_export(None)

    return Response(
        content=output_bytes,
        media_type=_MEDIA_TYPES.get(export_format, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="presentation.{export_format}"'},
    )


# -- Generation (async, optionally saved as a project if logged in) ----

@app.post("/generate/async")
async def generate_async(file: UploadFile = File(...), export_format: str = "pptx",
                          authorization: str | None = Header(default=None)):
    file_bytes = await file.read()
    user = _current_user(authorization)
    queue = registry.get_queue_adapter()
    job_id = queue.enqueue("generate", {
        "filename": file.filename or "upload.txt",
        "file_b64": base64.b64encode(file_bytes).decode("ascii"),
        "export_format": export_format,
        "owner_id": user.id if user else None,
    })
    return {"job_id": job_id, "status": "pending"}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    queue = registry.get_queue_adapter()
    job = queue.get_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    response = {"job_id": job.id, "status": job.status.value}
    if job.status == JobStatus.DONE and job.result:
        response["structure_source"] = job.result.get("structure_source")
        response["slide_count"] = job.result.get("slide_count")
        response["project_id"] = job.result.get("project_id")
    if job.status == JobStatus.FAILED:
        response["error"] = job.error
    return response


@app.get("/jobs/{job_id}/download")
def download_job(job_id: str):
    queue = registry.get_queue_adapter()
    job = queue.get_status(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=409, detail=f"job is {job.status.value}, not ready")
    file_bytes = base64.b64decode(job.result["file_b64"])
    fmt = job.result.get("export_format", "pptx")
    registry.get_analytics_adapter().record_export(job.payload.get("owner_id"))
    return Response(
        content=file_bytes,
        media_type=_MEDIA_TYPES.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="presentation.{fmt}"'},
    )


# -- Projects (requires auth — this is the reusable-project surface) ---

@app.get("/projects")
def list_projects(authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    projects = registry.get_storage_adapter().list_projects(user.id)
    return [
        {"project_id": p.project_id, "title": p.title, "updated_at": p.updated_at}
        for p in projects
    ]


@app.get("/projects/{project_id}")
def get_project(project_id: str, authorization: str | None = Header(default=None)):
    user = _current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    recipe = registry.get_storage_adapter().get_recipe(project_id, user.id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {
        "project_id": recipe.project_id,
        "language": recipe.language,
        "audience_type": recipe.audience_type,
        "slide_count": len(recipe.outline.slides),
        "slides": [{"order": s.order, "title": s.title} for s in recipe.outline.slides],
    }


@app.post("/projects/{project_id}/export")
def export_project(project_id: str, export_format: str = "pptx",
                    authorization: str | None = Header(default=None)):
    """Regenerate a file from a stored recipe — this is 'generate only
    on export' (Constitution Principle 5) applied to saved projects,
    not just fresh uploads."""
    user = _current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    recipe = registry.get_storage_adapter().get_recipe(project_id, user.id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="project not found")
    exporter = registry.get_export_adapter(export_format)
    file_bytes = exporter.export(recipe)
    registry.get_analytics_adapter().record_export(user.id)
    return Response(
        content=file_bytes,
        media_type=_MEDIA_TYPES.get(export_format, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="presentation.{export_format}"'},
    )


# -- Internal metrics (not public — check retention during the quiet
# launch per the earlier execution plan: "instrument a simple feedback
# signal and watch retention, not just signups") --------------------

@app.get("/internal/retention")
def internal_retention():
    summary = registry.get_analytics_adapter().get_retention_summary()
    return {
        "total_generations": summary.total_generations,
        "unique_logged_in_users": summary.unique_users,
        "returning_users": summary.returning_users,
        "exports_completed": summary.exports_completed,
        "note": "returning_users = generated on 2+ distinct days — "
                "the actual 'did they come back' signal, not just repeat "
                "same-session use.",
    }
