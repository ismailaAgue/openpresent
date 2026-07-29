# OPENPRESENT_CODEBASE.md

*The developer handbook. Read this before writing code. It explains how the codebase is organized and how to work in it — not what to build (that's `OpenPresent_Master.md` / `TECHNICAL_BLUEPRINT.md`) or why decisions were made (that's `ARCHITECTURE_DECISIONS.md`).*

*Precedence, always: `Constitution` → `TECHNICAL_BLUEPRINT.md` → `Cost Optimization` → `ARCHITECTURE_DECISIONS.md` → this file. If this file ever seems to conflict with one of those, those win — open an issue, don't silently follow this file instead.*

---

## 1. Repository Structure

```
openpresent/
├── frontend/              # Next.js + TypeScript — Layer 1 (web) and the interactive app
│   ├── app/                #   routing (static pages + dynamic app routes)
│   ├── components/         #   shared UI components
│   ├── lib/
│   │   └── api-client/     #   the ONLY place frontend code calls the backend
│   └── locales/            #   UI string dictionaries (Language System, Blueprint §8)
│
├── backend/                # FastAPI + Python — API Gateway + Layer 2 orchestration
│   ├── api/                 #   thin route handlers: validate input, enqueue jobs, return status
│   ├── ports/                #   one file per port — the interface definitions ONLY
│   │   ├── ingestion.py
│   │   ├── structure.py
│   │   ├── ai.py
│   │   ├── design.py
│   │   ├── export.py
│   │   ├── storage.py
│   │   ├── media.py
│   │   ├── queue.py
│   │   └── notification.py
│   ├── adapters/              #   concrete implementations, one subfolder per port
│   │   ├── ingestion/           #     pdf.py, docx.py, txt.py
│   │   ├── structure/           #     rule_based.py, ai_enhanced.py
│   │   ├── ai/                  #     null_adapter.py, local_model.py, hosted_api.py
│   │   ├── design/              #     rule_based.py
│   │   ├── export/              #     pptx.py, pdf.py, docx.py
│   │   ├── storage/              #     local_disk.py, s3_compatible.py
│   │   ├── media/                #     upload.py, stock_proxy.py
│   │   ├── queue/                #     db_backed.py, managed_queue.py
│   │   └── notification/         #     polling.py, websocket.py, email.py
│   ├── engines/                #   orchestration logic that CALLS ports — never adapters directly
│   ├── models/                  #   database models matching the Section 4 schema
│   └── workers/                #   Layer 2 job processors, pull from the Queue Port
│
├── database/                # migrations, schema definitions
├── storage/                  # local-disk adapter target in dev; not used in prod (S3-compatible instead)
├── shared/                    # types/schemas shared between frontend and backend (e.g. the Recipe format)
├── tests/
│   ├── contract/                #   one test suite PER PORT, run against every adapter of that port
│   ├── unit/
│   └── integration/
├── docs/
│   ├── OpenPresent_Master.md
│   ├── TECHNICAL_BLUEPRINT.md
│   ├── ARCHITECTURE_DECISIONS.md
│   └── OPENPRESENT_CODEBASE.md   # this file
└── docker/                    # local dev environment (Postgres, worker, backend, frontend)
```

**Why this shape:** the `ports/` vs `adapters/` split isn't cosmetic — it's the enforcement mechanism for the whole architecture. `ports/` contains only interfaces (abstract base classes / Python `Protocol`s), no implementation. `engines/` and `api/` are only ever allowed to import from `ports/`, never directly from `adapters/`. Adapter selection happens in one place (a config-driven registry, see Section 4), so nothing in the business logic ever hardcodes "we're using Ollama" or "we're using S3."

---

## 2. Package Responsibilities

| Package | Owns | Never does |
|---|---|---|
| `frontend/app` | Routing, page composition, SSG for static content | Business logic, direct database or AI access |
| `frontend/lib/api-client` | Every HTTP call to the backend | UI rendering |
| `backend/api` | Request validation, enqueueing jobs, returning status/results | Actual generation work — that's the worker's job, not the API's |
| `backend/ports` | Interface definitions only | Any implementation logic |
| `backend/adapters/*` | One concrete implementation of one port | Calling other adapters directly, or being called from anywhere except through its port |
| `backend/engines` | Orchestration — calling ports in the right order (e.g., Ingestion → Structure → Design → Export) | Knowing which adapter is active — that's the registry's job |
| `backend/workers` | Pulling jobs off the queue, invoking engines, writing results | Handling HTTP requests directly |
| `database/` | Schema and migrations | Business logic |
| `shared/` | Types both frontend and backend must agree on (Recipe format, API request/response shapes) | Anything backend- or frontend-specific |

**Rule of thumb:** if you're not sure which package something belongs in, ask "does this know about a *specific* provider/library (Ollama, python-pptx, S3), or does it only know about the *port's interface*?" Specific → `adapters/`. Interface-only → `ports/` or `engines/`.

---

## 3. Coding Standards

- **Every port is a `Protocol` (Python) or interface (TypeScript), not an abstract base class with logic in it.** Ports declare shape, adapters provide behavior.
- **Every adapter implements exactly one port, fully.** No partial implementations, no adapters that quietly also do something outside their port's contract.
- **No adapter imports another adapter.** If the Export adapter needs media, it goes through the Media Port, not by reaching into `adapters/media/` directly.
- **Every port has a documented "unavailable" behavior**, and for optional capabilities (AI, stock media) that behavior is a real, tested `NullAdapter` — not an exception someone has to remember to catch everywhere.
- **Config, not conditionals, selects adapters.** Never write `if environment == "prod": use_s3() else: use_local_disk()` inline in business logic — that decision lives in the adapter registry (Section 4) once, not scattered through the codebase.
- **Recipe format changes are additive and versioned.** Never repurpose an existing field; add a new one and bump `recipe_version` (per Technical Blueprint §5). Old recipes must still load.
- **Cost-impact comment required on any change touching AI calls, worker scaling, or storage retention.** A one-line comment or PR description field: "Cost impact: ..." — mirrors Constitution Principle 18 at the code level, not just the roadmap level.
- **No secrets, API keys, or provider credentials in code** — environment variables only, consistent with "adapter selection is config."

---

## 4. Port-and-Adapter Architecture, in Practice

**The registry pattern.** One module (`backend/adapters/registry.py`) reads configuration (environment variables or a config file) and returns the active adapter for each port. Everything else in the codebase asks the registry for "the current AI adapter" — it never imports a specific adapter class directly outside of `registry.py` and each adapter's own tests.

```
# Conceptual shape — not literal code, just the pattern
registry.get_adapter("ai")       -> returns NullAdapter, LocalModelAdapter, or HostedAPIAdapter
                                     based on config, at runtime
registry.get_adapter("export", format="pptx")  -> returns the PPTX adapter
```

**Why this matters day to day:** switching from Ollama to a different local model, or from local disk to S3, or turning AI off entirely for a maintenance window, is a config change and a restart — never a code change, never a deploy of modified business logic. This is what "replaceable component" (Constitution Principle 9, ADR-001) means concretely for someone writing code, not just for the architecture diagram.

**Adding a new adapter to an existing port** (e.g., a new export format, a new AI provider):
1. Implement the port's interface fully in a new file under the relevant `adapters/` subfolder.
2. Write contract tests (Section 8) — they already exist for the port; your new adapter must pass all of them.
3. Register it in `registry.py`, gated behind config.
4. Nothing else changes. If something else needs to change, that's a sign the port's interface was leaking implementation details and needs review — flag it, don't route around it.

---

## 5. Development Workflow

1. **Local environment via `docker/`** — Postgres, backend, worker, and frontend all run locally with `docker compose up`. AI defaults to the `NullAdapter` locally unless you're specifically working on AI integration, to keep local dev fast and free.
2. **Every change starts from an issue that names which port(s)/section(s) of the Blueprint it touches.** This isn't bureaucracy for its own sake — it's what makes "check against the Constitution and Blueprint before implementing" (Constitution's closing rule) actually practical rather than aspirational.
3. **Write the contract test first when touching a port**, or confirm existing contract tests still pass when touching an adapter.
4. **PR description includes a one-line cost-impact statement** (Section 3) for anything touching AI, storage, or worker scaling — copy the why/cost/replaceability habit from the Blueprint at PR scale, not just architecture-decision scale.
5. **If a change would violate a stated Constitution principle or Blueprint decision, it doesn't get silently "improved" — it gets raised as a new ADR proposal** (Section 10 of this handbook) before being merged.

---

## 6. Build Order

Matches `OpenPresent_Master.md` Section 5 (Roadmap) exactly — restated here as an implementation sequence:

1. **Phase 0:** repo scaffold, Postgres schema (`database/`), empty `ports/` interfaces, empty Layer 1/Layer 2 skeletons. Nothing functional yet — this phase is "the shape exists."
2. **Phase 1 (zero AI):** `adapters/ingestion/*`, `adapters/structure/rule_based.py`, `adapters/design/rule_based.py`, `adapters/export/pptx.py` + `pdf.py`, `adapters/storage/local_disk.py`. AI Port wired to `NullAdapter` only. **Do not start Phase 2 work until this produces a real, downloadable deck end-to-end.**
3. **Phase 2 (AI):** `adapters/ai/local_model.py` implementing the full capability set (structure, rewrite, translate, summarize, suggest per ADR-008), `adapters/queue/*` for real async processing, capacity-check logic in the AI Port.
4. **Phase 3 (real users):** auth, `frontend/app` dashboard/editor routes, `adapters/notification/polling.py`.
5. **Phase 4:** SEO/content pages in `frontend/app` (static routes), project-reuse logic in `engines/`, `adapters/queue/managed_queue.py` and `adapters/storage/s3_compatible.py` as traffic actually justifies the upgrade (Deployment Strategy, Blueprint §12).

**Do not build ahead of the current phase's evidence.** Phase 2's local model work shouldn't start before Phase 1's rule-based output has been judged genuinely good — that judgment is the actual gate, not the calendar.

---

## 7. Branch Strategy

Kept deliberately simple for a solo/small-team, $0-budget project — process overhead should stay proportional to team size.

- **`main`** — always deployable. Never committed to directly.
- **`feature/<port-or-area>-<short-description>`** — one feature branch per unit of work, named after the port or area it touches (e.g., `feature/export-docx-adapter`, `feature/ai-capacity-check`). This naming convention makes it immediately visible which part of the ports/adapters structure a branch affects.
- **PR into `main`**, contract tests must pass, cost-impact statement included where relevant (Section 5).
- **No long-lived branches.** If a feature branch outlives a couple of weeks, it's a sign the unit of work should have been split smaller — consistent with Constitution Principle 15 (ship the smallest real version first).
- **`hotfix/<description>`** for anything urgent (e.g., circuit breaker misfiring) — same PR discipline, expedited review.

---

## 8. Testing Strategy

**The core advantage of ports/adapters, realized in tests:** write one contract test suite per port, and every adapter of that port must pass it. This is the single highest-leverage testing investment in this codebase.

- **`tests/contract/`** — one suite per port (e.g., `test_export_port.py` defines "given a valid recipe, an Export adapter must return a valid file in its format, must raise a defined error on invalid input, must complete within X seconds"). Every adapter — PPTX, PDF, DOCX, and any future format — runs against the same suite. A new adapter that fails contract tests is not done, regardless of how its specific format-rendering code looks.
- **`tests/unit/`** — adapter-internal logic that isn't part of the port contract (e.g., the specific heuristics inside the rule-based Structure Engine).
- **`tests/integration/`** — full flows through `engines/` (Ingestion → Structure → Design → Export), run against the `NullAdapter` AI configuration by default (fast, free, no external dependency), with a smaller set run against real AI adapters in CI on a slower cadence.
- **Load testing the queue and worker pool** (flagged in the scaling review as essential, not optional) happens before each deployment-stage transition (Blueprint §12), simulating burst load (e.g., simulated exam-week spike) — not just before initial launch.
- **Security boundary tests** specifically target the boundaries named in Blueprint §11: malformed/oversized uploads rejected cleanly, AI Port never reachable with raw file content, cross-user data isolation enforced at the Storage Port level.

**A change is not considered complete until its contract tests pass** — this is what actually enforces "removing a plugin must never affect the rest of the application" (Constitution Principle 16) rather than that being just a nice sentence in a document.

---

## 9. How to Add a New Feature

1. **Locate it in the Roadmap** (`OpenPresent_Master.md` §5) or confirm it's genuinely new — if it's not on the roadmap and isn't a bug fix, it needs a cost-impact statement and a Constitution check before it becomes an issue at all.
2. **Identify which port(s) it touches.** Most features are either (a) a new adapter for an existing port, or (b) occasionally a new port entirely (rare — this is a bigger decision, see Section 10).
3. **Write the cost-impact statement first** (Section 3/5) — infrastructure, AI, storage. If you can't state it, that's a sign the feature isn't scoped enough to build yet.
4. **Write or confirm contract tests for the port** before writing the adapter implementation.
5. **Implement the adapter**, register it behind config, never modify calling code in `engines/` to special-case it.
6. **If it's genuinely a new port** (not just a new adapter): this changes the architecture, not just the codebase — it needs a new ADR entry in `ARCHITECTURE_DECISIONS.md` before merging, following the same why/cost/alternatives-considered format as every existing entry.

---

## 10. Ensuring Every Change Respects the Constitution and Blueprint

This is enforced at three points, not left to memory:

1. **At issue creation:** every issue names the Constitution principle(s) and Blueprint section(s) it relates to. If a proposed feature seems to conflict with one (e.g., "add a credit counter for power users" conflicts with Principle 6), that conflict is surfaced immediately, before any code is written — not discovered in review.
2. **At PR review:** the PR checklist includes "does this respect: AI-optional (Principle 2)? No visible limits for students (Principle 6)? Cost-impact stated (Principle 18)? Port boundaries respected (Section 4 of this handbook)?" A PR that fails any of these isn't merged until resolved.
3. **At architectural change:** any change big enough to need a new ADR (new port, changed cost ceiling, changed monetization mechanic, changed core promise) follows `ARCHITECTURE_DECISIONS.md`'s existing format exactly — Context, Decision, Why, Cost Impact, Alternatives Considered, Status — appended, never rewriting a prior entry. If a decision changes, the old ADR's status becomes `Superseded by ADR-0XX`, and the new entry explains why.

**The practical test for any contributor, including future-you six months from now:** if you can't point to which Constitution principle or Blueprint section justifies what you're about to build, stop and check `OpenPresent_Master.md` before writing code — that's what the precedence order at the top of this file is for.
