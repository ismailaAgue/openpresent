# OpenPresent — Phases 1–4

Phase 1 (rule-based core), Phase 2 (AI enhancement + async queue),
Phase 3 (auth + persistent, reusable projects), Phase 4 (AI-first
pivot, ADR-028; multi-provider images ADR-029; full multi-stage AI
pipeline + AI-driven layout planning ADR-030) — per
`docs/OpenPresent_Master.md` Roadmap and `docs/ARCHITECTURE_DECISIONS.md`.

**Verified end-to-end, including live HTTP, every phase:**
- Sync: upload -> real `.pptx`, $0 AI cost
- Async: enqueue -> worker -> poll -> download
- AI graceful degradation: every configured AI provider unreachable,
  generation still succeeds via the deterministic fallback path
- **Full account flow (Phase 3):** register -> login -> generate as an
  authenticated request -> worker persists the result as a reusable
  *project* (recipe, not the file — Constitution Principle 4) -> list
  projects -> per-owner data isolation confirmed (a project is
  invisible to any other account, and unauthenticated requests are
  correctly rejected with 401)
- **AI-first topic generation, full pipeline (ADR-028/030):** topic +
  slide count + audience + language -> a 5-stage AI pipeline (Planner/
  Strategy -> Outline -> Content -> AI-driven Layout Planning ->
  Quality Review) across a cascading multi-provider ladder, with a
  deterministic zero-AI fallback so generation never hard-fails
- **Multi-provider images (ADR-029):** Unsplash/Pexels/Pixabay/
  Wikimedia, relevance-scored, cached, deduplicated within a deck,
  with automatic provider fallback on quota exhaustion

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
}' -o presentation.zip
```

Response is a `.zip` containing `presentation.pptx` **and**
`speaker_notes.docx` (a separate Word document with every slide's
title, bullets, and speaker notes) by default — pass
`"bundle_speaker_notes": false` in the request body for a bare `.pptx`
instead.

Pipeline (ADR-030), 5 real AI stages, not one merged call:
Planner/Strategy -> Outline Structure -> Slide Content -> AI-driven
Layout Planning (which layout type + whether an image helps, per
slide, from the actual generated content) -> a $0 deterministic
Quality Validator (duplicate slides, excessive bullets, empty
sections, repeated ideas, missing closing slide, inconsistent
terminology, poor hierarchy, overflow risk) that auto-fixes what it
safely can, followed by an AI revision pass whenever real issues
remain -> the PPTX renderer. A Research stage (ADR-032, **on by
default**) feeds grounding facts into Strategy by merging results from
multiple providers — Wikipedia (real REST API, no key, always on),
plus Tavily and/or Brave Search when their keys are configured
(higher-quality/more current, ranked above Wikipedia). Facts are
combined and deduplicated across whichever providers are available,
not just the first one that responds — see ADR-032.
Presentation variety: the AI picks a narrative style from a catalog
of six (nudged by a random suggestion, not forced) and a visual theme
variant is chosen at random each generation. If every configured AI
provider is unavailable or every stage fails, a deterministic
topic-outline generator produces a valid (if generic) deck instead of
failing — the whole AI attempt is all-or-nothing per generation, never
a partially-AI, partially-broken deck.

**AI provider configuration** (`backend/adapters/registry.py`,
`get_ai_adapter()`):

Left unset (the default), every provider with credentials configured
is wired into a cascading composite, in this priority order — a stage
failing on one provider tries the next before falling back to the
deterministic path:

1. `OPENPRESENT_AI_BASE_URL` set — local model (Ollama-compatible),
   explicit opt-in only (a hosted Render deployment has no localhost
   model server). Also uses `OPENPRESENT_AI_MODEL` (default `qwen2.5:3b`).
2. `GEMINI_API_KEY` — **the default hosted provider.** Also uses
   `OPENPRESENT_GEMINI_MODEL` (default `gemini-3.5-flash`).
3. `GROQ_API_KEY` — Groq (fast, free-tier). Also uses
   `OPENPRESENT_GROQ_MODEL` (default `llama-3.1-8b-instant`).
4. `OPENROUTER_API_KEY` — OpenRouter (aggregates many models,
   including free-tier). Also uses `OPENPRESENT_OPENROUTER_MODEL`
   (default `openrouter/free`).
5. `HUGGINGFACE_API_KEY` — HuggingFace Inference Providers. Also uses
   `OPENPRESENT_HUGGINGFACE_MODEL` (default `meta-llama/Llama-3.1-8B-Instruct`).

`OPENPRESENT_AI_ADAPTER=<local_model|gemini|groq|openrouter|huggingface|null>`
forces exactly one provider (bypasses the composite) — useful for
testing a single provider in isolation. No provider configured at all
-> `NullAdapter`, $0, no dependency.

**Image provider configuration** — any/all of these can be set
together; `MultiProviderMediaAdapter` queries them in this order,
falling back automatically on quota exhaustion or failure:

1. `OPENPRESENT_UNSPLASH_ACCESS_KEY`
2. `OPENPRESENT_PEXELS_API_KEY`
3. `OPENPRESENT_PIXABAY_API_KEY`
4. Wikimedia Commons — no key needed, always on unless
   `OPENPRESENT_DISABLE_WIKIMEDIA=true`

**Optional extras:**
- **Research providers (ADR-032, on by default — Wikipedia needs no
  key):**
  - `TAVILY_API_KEY` — highest priority when set, purpose-built for
    LLM grounding
  - `BRAVE_SEARCH_API_KEY` — second priority, live web index
  - Wikipedia — always on, no key, real REST API (not scraping)
  - `OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH=true` — optional bonus
    free source (best-effort HTML scraping, no longer the default)
  - `OPENPRESENT_RESEARCH_ADAPTER=null` — fully disables the Research
    stage
- `SENTRY_DSN` — enables structured monitoring (AI/image/render/export
  failures, breadcrumbs through the pipeline). Works with any
  Sentry-protocol-compatible backend interchangeably — Bugsink (this
  deployment's choice: higher hosted event quota, lighter self-host
  footprint than alternatives), GlitchTip, self-hosted Sentry, or
  Sentry SaaS — same `sentry-sdk` package, same DSN-based
  configuration, zero code differences either way. No-op if unset, and
  a no-op if `sentry-sdk` isn't installed even with a DSN set. Set
  `SENTRY_TRACES_SAMPLE_RATE=0` alongside it if using Bugsink
  specifically (it doesn't process performance-tracing data).

## Quick start

```bash
pip install -r requirements.txt --break-system-packages

export OPENPRESENT_QUEUE_DB=./queue.db
export OPENPRESENT_STORAGE_DB=./storage.db
export OPENPRESENT_AUTH_DB=./auth.db

# AI-first generation (optional — omit to run entirely on $0 fallbacks)
export GEMINI_API_KEY=your-gemini-api-key
# export GROQ_API_KEY=...           # additional fallback provider
# export OPENROUTER_API_KEY=...     # additional fallback provider

# Real stock photography (optional — omit to run with Wikimedia only)
export OPENPRESENT_UNSPLASH_ACCESS_KEY=your-unsplash-access-key
# export OPENPRESENT_PEXELS_API_KEY=...
# export OPENPRESENT_PIXABAY_API_KEY=...

# Research grounding (on by default via Wikipedia — no key needed;
# these two are optional upgrades, higher priority when set)
# export TAVILY_API_KEY=...
# export BRAVE_SEARCH_API_KEY=...

# Monitoring (optional — Bugsink, GlitchTip, or Sentry all work, same env var)
# export SENTRY_DSN=...
# export SENTRY_TRACES_SAMPLE_RATE=0   # set to 0 for Bugsink specifically

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

# Or generate from a document, same auth/project pattern — audience,
# language, and a target slide count are all optional (ADR-034); when
# language isn't English, the outline is genuinely translated, not just
# tagged with a locale
curl -X POST "localhost:8000/generate/async?audience_type=business&language=fr&target_slide_count=10" \
  -H "Authorization: Bearer $TOKEN" -F "file=@essay.txt"

# Your reusable projects
curl localhost:8000/projects -H "Authorization: Bearer $TOKEN"
curl -X POST "localhost:8000/projects/<project_id>/export?export_format=pptx" \
  -H "Authorization: Bearer $TOKEN" -o out.pptx

# Slide-level editing / partial regeneration (ADR-038) — only this one
# slide changes, every other slide in the deck is untouched
curl -X PATCH "localhost:8000/projects/<project_id>/slides/2" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title": "A Better Title", "bullets": ["Point one", "Point two"]}'
curl -X POST "localhost:8000/projects/<project_id>/slides/2/regenerate" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"instructions": "make this more concise"}'
```

Anonymous use (no account) still works via both sync endpoints
(`/generate` and `/generate/topic`) — accounts are required only to
save/reuse projects, never to generate a presentation. This matches
the "no-account-required, no visible limits" core promise.

Slide editing requires a saved project (an account), same as export —
`PATCH .../slides/{order}` never needs AI configured; `POST
.../slides/{order}/regenerate` returns a `503` if no AI provider is
available (there's no honest deterministic substitute for "rewrite
this one slide," unlike full-deck generation's topic-template
fallback — see ADR-038).

## CI / Continuous Integration

Two separate GitHub Actions workflows (ADR-036):

- **`.github/workflows/ci.yml`** — runs on every push and pull request.
  The full 241-test hermetic suite plus a frontend typecheck/build.
  Needs zero secrets/configuration to work — just push, it runs.
- **`.github/workflows/provider-drift-check.yml`** — runs daily
  (06:00 UTC) plus on-demand via the Actions tab's "Run workflow"
  button. Makes real calls against whichever provider APIs you've
  configured secrets for, and automatically opens (or comments on/
  closes) a GitHub issue labeled `provider-drift` when a provider
  breaks or recovers. To enable it for a given provider, add the
  matching secret in **Settings -> Secrets and variables -> Actions**:
  `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`,
  `HUGGINGFACE_API_KEY`, `OPENPRESENT_UNSPLASH_ACCESS_KEY`,
  `OPENPRESENT_PEXELS_API_KEY`, `OPENPRESENT_PIXABAY_API_KEY`,
  `TAVILY_API_KEY`, `BRAVE_SEARCH_API_KEY`. Any you skip just means
  that provider's checks skip too (Wikipedia and Wikimedia need no key
  and always run, since they're this codebase's universal fallbacks).

To actually block a merge on CI failure, add a branch protection rule
in **Settings -> Branches** requiring the `backend-tests` and
`frontend-build` checks to pass — this is a one-time GitHub repo
setting, not something either workflow file configures on its own.

## Run tests

```bash
# Hermetic suite (what CI runs on every push — no API keys, no live
# network, no third-party dependency at all — see .github/workflows/ci.yml)
PYTHONPATH=. python -m pytest tests/ --ignore=tests/smoke -v

# Live provider drift check (ADR-036) — real network calls against
# whichever provider API keys you have set in your environment; any
# key you don't have just skips that provider's tests. Not run in the
# main CI job; see .github/workflows/provider-drift-check.yml for the
# scheduled version with automatic GitHub issue filing on failure.
PYTHONPATH=. python -m pytest tests/smoke -v
```

283 tests pass across ingestion, structure engine, AI Port (real
cross-provider cascading and failure logging for the document-upload
enhancement flow, not just the topic-first pipeline — ADR-033; correct
model defaults, Cloudflare-safe User-Agent headers, and JSON-mode
threading verified at the real HTTP-request-object level, not just
mocked — ADR-034), the full 5-stage AI Pipeline Port (Gemini, local
model, Groq, OpenRouter, HuggingFace, plus composite cascading
fallback), quality validator (including the checks added in
ADR-030/031), multi-provider image router (relevance scoring, caching,
dedup, quota fallback), the multi-provider Research composite
(Tavily/Brave/Wikipedia/DuckDuckGo, merge/dedup/cap behavior —
ADR-032), document-flow controls (audience/language/target slide
count, real translation — ADR-034), structured monitoring no-op
behavior, export bundling (PPTX + speaker notes DOCX), Queue Port,
Storage Port (including per-owner isolation), Auth Port, engine-level
integration tests for both generation flows, and 18 real HTTP-level
integration tests (`tests/integration/test_api_http.py`, ADR-035) —
genuine requests through the actual FastAPI stack, including full
async round trips against the real in-process worker thread, not
mocked engine calls. `tests/conftest.py` (ADR-037) enforces this
hermeticity automatically for every test: `get_ai_adapter`,
`get_media_adapter`, and `get_research_adapter` default to their Null
variants across the whole suite unless a test explicitly overrides
one — closing a real gap where several tests only "looked" hermetic
in a sandboxed dev environment with no route to wikipedia.org/
wikimedia.org, then failed the first time they ran against a real
network in CI.

## What's NOT here yet (by design — see Roadmap)

- PDF export adapter (DOCX now exists — speaker notes, ADR-030)
- Managed Postgres (SQLite used for local dev; swap is a
  connection-string change per ADR-006) — Neon Postgres in production
  via `DATABASE_URL`, per ADR-018
- Cost circuit breaker enforcement (Blueprint Section 16 — designed,
  not yet wired into the AI call path) — now more relevant than before
  given ADR-030's up-to-5-6-calls-per-generation pipeline
- Password hashing is stdlib SHA-256+salt for this dev-stage adapter;
  a production Auth adapter should use bcrypt/argon2 — a contained
  adapter swap, not a port change
- Every AI/image/research provider adapter's HERMETIC tests (tests/
  contract/, tests/integration/) are verified against mocked HTTP
  responses, by design — that's what makes them fast and free to run
  on every push. Live verification (ADR-036) happens separately: see
  `.github/workflows/provider-drift-check.yml`, a scheduled workflow
  against real provider APIs with real credentials, which automatically
  files (and auto-closes) a GitHub issue on failure/recovery.
- DuckDuckGo research scraping is best-effort by design (no real
  search API integrated) — off by default for this reason
- CI (`.github/workflows/ci.yml`) runs the hermetic 241-test suite plus
  a frontend typecheck/build on every push and PR — requires zero
  secrets, since the whole suite is hermetic by construction. What it
  does NOT do: nothing yet blocks a merge on CI failure (no branch
  protection rule configured at the GitHub repo-settings level — that's
  a one-time manual step in Settings -> Branches, not something a
  workflow file can configure on its own).

## Next ADR

ADR-031 should log real-world results once the full multi-provider,
multi-stage pipeline is live in production — actual per-provider
latency and cascade-fallback frequency, whether Groq/OpenRouter/
HuggingFace's free-tier defaults hold up, and whether the AI-driven
layout planning stage's slide-type distribution looks meaningfully
different from the old rule-based classifier's — see
`docs/ARCHITECTURE_DECISIONS.md`.
