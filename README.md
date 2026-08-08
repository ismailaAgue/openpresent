# OpenPresent — Phases 1–4

Phase 1 (rule-based core), Phase 2 (AI enhancement + async queue),
Phase 3 (auth + persistent, reusable projects), Phase 4 (AI-first
pivot: topic-first generation, ADR-028) — per
`docs/OpenPresent_Master.md` Roadmap and `docs/ARCHITECTURE_DECISIONS.md`.

**Verified end-to-end, including live HTTP, every phase:**
- Sync: upload -> real `.pptx`, $0 AI cost
- Async: enqueue -> worker -> poll -> download
- AI graceful degradation: `LocalModelAdapter` configured, no model
  server running, `/health` correctly reports unavailable, generation
  still succeeds via rule-based fallback
- **Full account flow (Phase 3):** register -> login -> generate as an
  authenticated request -> worker persists the result as a reusable
  *project* (recipe, not the file — Constitution Principle 4) -> list
  projects -> per-owner data isolation confirmed (a project is
  invisible to any other account, and unauthenticated requests are
  correctly rejected with 401)
- **AI-first topic generation (Phase 4, ADR-028):** topic + slide
  count + audience + language -> a complete deck with no source
  document, via Gemini (default hosted provider) or a local model,
  with a deterministic zero-AI fallback so this never hard-fails

## AI-first generation (Phase 4)

`POST /generate/topic` (sync) and `POST /generate/topic/async` +
`/jobs/{id}` generate a presentation directly from a topic — no
document upload required. This is now the primary flow on the
frontend homepage; document upload remains available as a second tab.

```bash
curl -X POST localhost:8000/generate/topic -H "Content-Type: application/json" -d '{
  "topic": "The causes and effects of the French Revolution",
  "slide_count": 10,
  "audience_type": "student_school",
  "language": "en"
}' -o presentation.pptx
```

Pipeline: one structured AI call plans + drafts the whole outline
(title through closing slide, with speaker notes) -> the existing,
unchanged Design Engine assigns layout/image queries deterministically
(AI never touches formatting, per the spec) -> a $0 rule-based quality
validator checks for duplicate slides, excessive bullets, empty
sections, repeated ideas, and a missing closing slide, auto-fixing
what it safely can -> the existing, unchanged PPTX renderer. If no AI
provider is configured or reachable, a deterministic topic-outline
generator produces a valid (if generic) deck instead of failing.

**AI provider configuration** (`backend/adapters/registry.py`,
`get_ai_adapter()`), checked in this order:

1. `OPENPRESENT_AI_ADAPTER=local_model` — explicit opt-in only (a
   hosted Render deployment has no localhost model server). Also uses
   `OPENPRESENT_AI_BASE_URL` (default `http://localhost:11434`) and
   `OPENPRESENT_AI_MODEL` (default `qwen2.5:3b`).
2. `OPENPRESENT_AI_ADAPTER=gemini`, or left unset with `GEMINI_API_KEY`
   present — **the default hosted provider.** Also uses
   `OPENPRESENT_GEMINI_MODEL` (default `gemini-2.0-flash`).
3. Otherwise — `NullAdapter`, the original $0/no-dependency default.

Optional: `OPENPRESENT_AI_QUALITY_REVIEW=true` enables one extra,
bounded AI revision pass when the deterministic validator finds issues
it can't fix itself (off by default — Cost Policy).

## Quick start

```bash
pip install -r requirements.txt --break-system-packages

export OPENPRESENT_QUEUE_DB=./queue.db
export OPENPRESENT_STORAGE_DB=./storage.db
export OPENPRESENT_AUTH_DB=./auth.db

# AI-first generation (optional — omit to run entirely on $0 fallbacks)
export GEMINI_API_KEY=your-gemini-api-key

# Real stock photography (optional — omit to run with no images)
export OPENPRESENT_UNSPLASH_ACCESS_KEY=your-unsplash-access-key

# Terminal 1 — API
PYTHONPATH=. uvicorn backend.api.main:app --reload

# Terminal 2 — worker (same DB files)
PYTHONPATH=. python -c \
  "from backend.workers.generation_worker import run_worker_loop; run_worker_loop()"
```

## Example flow

```bash
# Register + login
curl -X POST localhost:8000/auth/register -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}'
TOKEN=$(curl -s -X POST localhost:8000/auth/login -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"..."}' | python3 -c "import sys,json;print(json.load(sys.stdin)['session_token'])")

# Generate from a topic, authenticated -> saved as a project automatically
curl -X POST localhost:8000/generate/topic/async -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"topic":"Intro to machine learning","slide_count":8}'
# -> poll /jobs/<id> until status is "done", note the project_id

# Or generate from a document, same auth/project pattern
curl -X POST localhost:8000/generate/async -H "Authorization: Bearer $TOKEN" -F "file=@essay.txt"

# Your reusable projects
curl localhost:8000/projects -H "Authorization: Bearer $TOKEN"
curl -X POST "localhost:8000/projects/<project_id>/export?export_format=pptx" \
  -H "Authorization: Bearer $TOKEN" -o out.pptx
```

Anonymous use (no account) still works via both sync endpoints
(`/generate` and `/generate/topic`) — accounts are required only to
save/reuse projects, never to generate a presentation. This matches
the "no-account-required, no visible limits" core promise.

## Run tests

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

114 tests pass across ingestion, structure engine, AI Port, AI
Pipeline Port (Gemini + local model, topic-first generation), quality
validator, Queue Port, Storage Port (including per-owner isolation),
Auth Port, and full integration tests for both generation flows.

## What's NOT here yet (by design — see Roadmap)

- PDF/DOCX export adapters
- Managed Postgres (SQLite used for local dev; swap is a
  connection-string change per ADR-006) — Neon Postgres in production
  via `DATABASE_URL`, per ADR-018
- Cost circuit breaker enforcement (Blueprint Section 16 — designed,
  not yet wired into the AI call path)
- Password hashing is stdlib SHA-256+salt for this dev-stage adapter;
  a production Auth adapter should use bcrypt/argon2 — a contained
  adapter swap, not a port change
- Gemini's live API is verified against mocked HTTP responses in
  tests (no network access in this environment) — first real
  verification happens on deployment with a genuine `GEMINI_API_KEY`

## Next ADR

ADR-029 should log real-world results once Gemini is live in
production (actual latency, JSON-mode reliability, free-tier quota
behavior under real traffic) — see `docs/ARCHITECTURE_DECISIONS.md`.
