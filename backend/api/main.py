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
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.engines.generate import generate_presentation
from backend.engines.ai_generate import generate_presentation_from_topic
from backend.engines.export_bundle import build_export_bundle
from backend.engines.edit_slide import (
    edit_slide_manually, regenerate_slide_ai,
    ProjectNotFoundError, SlideNotFoundError, AIUnavailableError,
)
from backend.models.recipe import BlockType
from backend.ports.ingestion import UnsupportedFileTypeError, CorruptFileError
from backend.ports.export import UnsupportedFormatError
from backend.ports.queue import JobStatus
from backend.ports.auth import EmailAlreadyRegisteredError, InvalidCredentialsError
from backend.monitoring.sentry_setup import init_sentry, is_active as sentry_is_active

MIN_SLIDE_COUNT = 3
MAX_SLIDE_COUNT = 30

init_sentry()  # no-op unless SENTRY_DSN is configured — see monitoring/sentry_setup.py


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


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Modern replacement for the deprecated @app.on_event("startup")
    # decorator (FastAPI's own recommended migration) — same behavior,
    # same daemon-thread worker, just the current API shape. Nothing
    # runs on shutdown; the daemon thread is killed with the process.
    if os.environ.get("OPENPRESENT_INPROCESS_WORKER", "true").lower() == "true":
        thread = threading.Thread(target=_in_process_worker_loop, daemon=True)
        thread.start()
    yield


app = FastAPI(title="OpenPresent API — Phase 4", lifespan=_lifespan)

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
    # ADR-039 fix: without this, custom response headers
    # (X-Project-Id, X-Structure-Source, X-Quality-Score) are invisible
    # to frontend JavaScript on cross-origin requests (Vercel frontend
    # -> Render backend are different origins) — browsers only expose a
    # small "safe" default set (Content-Type, Content-Length, etc.) for
    # cross-origin responses unless the server explicitly lists more.
    # Found while wiring up X-Project-Id for the homepage's "view and
    # edit this presentation" link — without this line, that header
    # would have been present in the raw HTTP response but silently
    # read as null by every browser, everywhere, always.
    expose_headers=["X-Project-Id", "X-Structure-Source", "X-Quality-Score"],
)

_MEDIA_TYPES = {"pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


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


class TopicGenerateRequest(BaseModel):
    topic: str
    slide_count: int = 10
    audience_type: str = "general"
    language: str = "en"
    tone: str = "professional"
    export_format: str = "pptx"
    bundle_speaker_notes: bool = True


class SlideEditRequest(BaseModel):
    """PATCH /projects/{project_id}/slides/{slide_order} — ADR-038.
    Every field optional; only supplied ones are changed. At least one
    must be given (enforced in edit_slide_manually, not here, so the
    error message comes from one place)."""
    title: str | None = None
    bullets: list[str] | None = None
    notes: str | None = None


class SlideRegenerateRequest(BaseModel):
    """POST /projects/{project_id}/slides/{slide_order}/regenerate — ADR-038."""
    instructions: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/")
def root():
    """Render (and other infra) probes '/' by default unless a
    Health Check Path is explicitly configured — this exists purely
    so that shows up as a normal 200 instead of a 404 in the logs.
    Real health/config verification lives at /health."""
    return {"service": "OpenPresent API", "status": "ok", "health_check": "/health"}


@app.get("/health")
def health():
    ai = registry.get_ai_adapter()
    ai_pipeline = registry.get_ai_pipeline_adapter()
    media = registry.get_media_adapter()
    research = registry.get_research_adapter()
    queue = registry.get_queue_adapter()
    auth = registry.get_auth_adapter()
    storage = registry.get_storage_adapter()

    # Lists the actual provider classes wired into the composite/router
    # (not just "CompositeAIAdapter"/"MultiProviderMediaAdapter") so a
    # deployment can be verified from /health alone — ADR-030/029.
    ai_providers = [type(a).__name__ for a in getattr(ai, "adapters", [])] or [type(ai).__name__]
    media_providers = [p.name for p in getattr(media, "providers", [])]
    research_providers = [type(p).__name__ for p in getattr(research, "providers", [])]

    return {
        "status": "ok",
        "phase": 4,  # Phase 4: AI-first pivot (ADR-028), multi-provider images (ADR-029),
                     # full multi-stage AI pipeline + AI-driven layout planning (ADR-030),
                     # multi-provider research (ADR-032)
        "ai_adapter": type(ai).__name__,
        "ai_providers_configured": ai_providers,
        "ai_available": ai.is_available(),
        "ai_pipeline_available": ai_pipeline.is_available(),
        "media_adapter": type(media).__name__,
        "media_providers_configured": media_providers,
        "media_available": media.is_available(),
        "research_adapter": type(research).__name__,
        "research_providers_configured": research_providers,
        "research_available": research.is_available(),
        "sentry_active": sentry_is_active(),
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
async def generate(file: UploadFile = File(...), export_format: str = "pptx",
                    bundle_speaker_notes: bool = True,
                    audience_type: str = "student_school", language: str = "en",
                    target_slide_count: int | None = None,
                    authorization: str | None = Header(default=None)):
    # ADR-039 fix: previously this endpoint never accepted or checked
    # auth at all, and never saved a project — only /generate/async
    # did. Since the homepage UI calls THIS endpoint (the sync one) for
    # its primary generation flow, a logged-in user generating from the
    # website got nothing saved, nothing to edit, no project ever
    # created — the slide-editing feature (ADR-038) was completely
    # unreachable from actual product usage even though it worked
    # correctly at the API level. Fixed by giving sync generation the
    # same "save if logged in" behavior async already had.
    user = _current_user(authorization)
    file_bytes = await file.read()
    try:
        recipe, output_bytes = generate_presentation(
            file_bytes=file_bytes,
            filename=file.filename or "upload.txt",
            export_format=export_format,
            audience_type=audience_type,
            language=language,
            target_slide_count=target_slide_count,
        )
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CorruptFileError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    owner_id = user.id if user else None
    project_id = None
    if owner_id:
        title = recipe.outline.slides[0].title if recipe.outline.slides else "Untitled"
        project_id = registry.get_storage_adapter().save_recipe(owner_id, recipe, title)

    registry.get_analytics_adapter().record_generation(owner_id, recipe.outline.structure_source.value)
    registry.get_analytics_adapter().record_export(owner_id)

    extra_headers = {"X-Project-Id": project_id} if project_id else {}

    # ADR-029: bundle the primary export with a speaker-notes .docx
    # companion by default — a real Word document, not notes crammed
    # into the pptx's visible body text (see the pptx_adapter.py fix
    # from the same ADR). bundle_speaker_notes=false opts back into a
    # single bare file, e.g. for programmatic callers that only want
    # the pptx bytes directly.
    if bundle_speaker_notes and export_format == "pptx":
        zip_bytes = build_export_bundle(recipe, output_bytes, export_format)
        return Response(
            content=zip_bytes, media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="presentation.zip"', **extra_headers},
        )

    return Response(
        content=output_bytes,
        media_type=_MEDIA_TYPES.get(export_format, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="presentation.{export_format}"', **extra_headers},
    )


# -- Generation (async, optionally saved as a project if logged in) ----

# -- Generation from a topic (AI-first, ADR-028: no source document) ---

def _clean_slide_count(n: int) -> int:
    return max(MIN_SLIDE_COUNT, min(n, MAX_SLIDE_COUNT))


@app.post("/generate/topic")
def generate_from_topic(req: TopicGenerateRequest, authorization: str | None = Header(default=None)):
    if not req.topic or not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")
    # ADR-039 fix — same gap, same fix as sync /generate above: this
    # endpoint never saved a project before, so the homepage's topic
    # form (the primary "AI-first" flow) never produced anything
    # editable even for a logged-in user.
    user = _current_user(authorization)
    try:
        recipe, output_bytes, quality = generate_presentation_from_topic(
            topic=req.topic,
            slide_count=_clean_slide_count(req.slide_count),
            audience_type=req.audience_type,
            language=req.language,
            tone=req.tone,
            export_format=req.export_format,
        )
    except UnsupportedFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    owner_id = user.id if user else None
    project_id = None
    if owner_id:
        title = recipe.outline.slides[0].title if recipe.outline.slides else "Untitled"
        project_id = registry.get_storage_adapter().save_recipe(owner_id, recipe, title)

    registry.get_analytics_adapter().record_generation(owner_id, recipe.outline.structure_source.value)
    registry.get_analytics_adapter().record_export(owner_id)

    headers = {
        "X-Structure-Source": recipe.outline.structure_source.value,
        "X-Quality-Score": str(quality.score),
    }
    if project_id:
        headers["X-Project-Id"] = project_id

    if req.bundle_speaker_notes and req.export_format == "pptx":
        zip_bytes = build_export_bundle(recipe, output_bytes, req.export_format)
        headers["Content-Disposition"] = 'attachment; filename="presentation.zip"'
        return Response(content=zip_bytes, media_type="application/zip", headers=headers)

    headers["Content-Disposition"] = f'attachment; filename="presentation.{req.export_format}"'
    return Response(
        content=output_bytes,
        media_type=_MEDIA_TYPES.get(req.export_format, "application/octet-stream"),
        headers=headers,
    )


@app.post("/generate/topic/async")
def generate_from_topic_async(req: TopicGenerateRequest,
                               authorization: str | None = Header(default=None)):
    if not req.topic or not req.topic.strip():
        raise HTTPException(status_code=400, detail="topic is required")
    user = _current_user(authorization)
    queue = registry.get_queue_adapter()
    job_id = queue.enqueue("generate_topic", {
        "topic": req.topic,
        "slide_count": _clean_slide_count(req.slide_count),
        "audience_type": req.audience_type,
        "language": req.language,
        "tone": req.tone,
        "export_format": req.export_format,
        "bundle_speaker_notes": req.bundle_speaker_notes,
        "owner_id": user.id if user else None,
    })
    return {"job_id": job_id, "status": "pending"}


@app.post("/generate/async")
async def generate_async(file: UploadFile = File(...), export_format: str = "pptx",
                          bundle_speaker_notes: bool = True,
                          audience_type: str = "student_school", language: str = "en",
                          target_slide_count: int | None = None,
                          authorization: str | None = Header(default=None)):
    file_bytes = await file.read()
    user = _current_user(authorization)
    queue = registry.get_queue_adapter()
    job_id = queue.enqueue("generate", {
        "filename": file.filename or "upload.txt",
        "file_b64": base64.b64encode(file_bytes).decode("ascii"),
        "export_format": export_format,
        "bundle_speaker_notes": bundle_speaker_notes,
        "audience_type": audience_type,
        "language": language,
        "target_slide_count": target_slide_count,
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
    if job.status == JobStatus.RUNNING and job.stage:
        response["stage"] = job.stage  # ADR-040 — best-effort, topic generation only
    if job.status == JobStatus.DONE and job.result:
        response["structure_source"] = job.result.get("structure_source")
        response["slide_count"] = job.result.get("slide_count")
        response["project_id"] = job.result.get("project_id")
        if "quality_score" in job.result:
            response["quality_score"] = job.result.get("quality_score")
            response["quality_issues"] = job.result.get("quality_issues", [])
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

    if job.result.get("is_bundle"):
        return Response(
            content=file_bytes, media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="presentation.zip"'},
        )
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


def _slide_detail(slide) -> dict:
    return {
        "order": slide.order,
        "title": slide.title,
        "bullets": [b.text for b in slide.content_blocks if b.type == BlockType.BULLET],
        "notes": next((b.text for b in slide.content_blocks if b.type == BlockType.NOTE), ""),
        "layout_type": slide.layout_type,
        "image_query": slide.image_query,
    }


@app.get("/projects/{project_id}/slides/{slide_order}")
def get_slide(project_id: str, slide_order: int, authorization: str | None = Header(default=None)):
    """ADR-038. Full detail for one slide — bullets/notes/layout, not
    just the title summary GET /projects/{project_id} gives — meant
    for an editing UI to load before showing edit/regenerate controls."""
    user = _current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    recipe = registry.get_storage_adapter().get_recipe(project_id, user.id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="project not found")
    for slide in recipe.outline.slides:
        if slide.order == slide_order:
            return _slide_detail(slide)
    raise HTTPException(status_code=404, detail="slide not found")


@app.patch("/projects/{project_id}/slides/{slide_order}")
def edit_slide(project_id: str, slide_order: int, req: SlideEditRequest,
                authorization: str | None = Header(default=None)):
    """ADR-038, manual (no-AI) slide edit — always available regardless
    of AI configuration. Only supplied fields change; other slides in
    the deck are never touched. Call POST .../export afterward (or
    GET this slide again) to see the result — this endpoint updates
    the stored project, it doesn't return a file."""
    user = _current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    try:
        recipe = edit_slide_manually(project_id, slide_order, user.id,
                                      title=req.title, bullets=req.bullets, notes=req.notes)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    except SlideNotFoundError:
        raise HTTPException(status_code=404, detail="slide not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    slide = next(s for s in recipe.outline.slides if s.order == slide_order)
    return _slide_detail(slide)


@app.post("/projects/{project_id}/slides/{slide_order}/regenerate")
def regenerate_slide(project_id: str, slide_order: int, req: SlideRegenerateRequest,
                      authorization: str | None = Header(default=None)):
    """ADR-038, AI-assisted partial regeneration — rewrites exactly
    this one slide, every other slide in the deck stays untouched
    (this is the whole point: not a full deck re-run for a one-slide
    tweak). Requires an AI provider to be configured; use PATCH on
    this same URL instead for a manual, no-AI edit."""
    user = _current_user(authorization)
    if user is None:
        raise HTTPException(status_code=401, detail="login required")
    try:
        recipe = regenerate_slide_ai(project_id, slide_order, user.id, instructions=req.instructions)
    except ProjectNotFoundError:
        raise HTTPException(status_code=404, detail="project not found")
    except SlideNotFoundError:
        raise HTTPException(status_code=404, detail="slide not found")
    except AIUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    slide = next(s for s in recipe.outline.slides if s.order == slide_order)
    return _slide_detail(slide)


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
