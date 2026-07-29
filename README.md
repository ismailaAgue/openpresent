# OpenPresent — Phases 1–3

Phase 1 (rule-based core), Phase 2 (AI enhancement + async queue),
Phase 3 (auth + persistent, reusable projects) — per
`docs/OpenPresent_Master.md` Roadmap.

**Verified end-to-end, including live HTTP, every phase:**
- Sync: upload -> real `.pptx`, $0 AI cost
- Async: enqueue -> worker -> poll -> download
- AI graceful degradation: `LocalModelAdapter` configured, no model
  server running, `/health` correctly reports unavailable, generation
  still succeeds via rule-based fallback
- **Full account flow (Phase 3, just proven live):** register -> login
  -> generate as an authenticated request -> worker persists the
  result as a reusable *project* (recipe, not the file — Constitution
  Principle 4) -> list projects -> per-owner data isolation confirmed
  (a project is invisible to any other account, and unauthenticated
  requests are correctly rejected with 401)

## Quick start

```bash
pip install -r requirements.txt --break-system-packages

export OPENPRESENT_QUEUE_DB=./queue.db
export OPENPRESENT_STORAGE_DB=./storage.db
export OPENPRESENT_AUTH_DB=./auth.db

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

# Generate, authenticated -> saved as a project automatically
curl -X POST localhost:8000/generate/async -H "Authorization: Bearer $TOKEN" -F "file=@essay.txt"
# -> poll /jobs/<id> until status is "done", note the project_id

# Your reusable projects
curl localhost:8000/projects -H "Authorization: Bearer $TOKEN"
curl -X POST "localhost:8000/projects/<project_id>/export?export_format=pptx" \
  -H "Authorization: Bearer $TOKEN" -o out.pptx
```

Anonymous use (no account) still works via the original sync
`/generate` endpoint — accounts are required only to save/reuse
projects, never to generate a presentation. This matches the
"no-account-required, no visible limits" core promise.

## Run tests

```bash
PYTHONPATH=. python -m pytest tests/ -v
```

33 tests pass across ingestion, structure engine, AI Port, Queue Port,
Storage Port (including per-owner isolation), Auth Port, and one full
integration test.

## What's NOT here yet (by design — see Roadmap)

- Frontend (Next.js dashboard/editor — Phase 3 also calls for this;
  only the backend half is built so far)
- PDF/DOCX export adapters
- Managed Postgres (SQLite used for local dev; swap is a
  connection-string change per ADR-006)
- Cost circuit breaker enforcement (Blueprint Section 16 — designed,
  not yet wired into the AI call path)
- Password hashing is stdlib SHA-256+salt for this dev-stage adapter;
  a production Auth adapter should use bcrypt/argon2 — a contained
  adapter swap, not a port change

## Next ADR

ADR-014 should log the persistence/ownership model now that Storage
and Auth Ports are implemented — see `docs/ARCHITECTURE_DECISIONS.md`.
