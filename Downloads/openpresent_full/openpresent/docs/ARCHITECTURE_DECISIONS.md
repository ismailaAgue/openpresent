# ARCHITECTURE_DECISIONS.md

A running log of significant OpenPresent design decisions. Every entry follows the same format: **Context → Decision → Why → Cost Impact → Alternatives Considered → Status**. New entries are appended, never edited in place — if a decision changes, a new entry supersedes the old one, and the old one's status is updated to `Superseded by ADR-00X`.

Checked against, in order, before any implementation: **Constitution → Technical Blueprint → Cost Optimization document → this log.**

---

## ADR-001 — Ports-and-Adapters Architecture

**Context:** Product must satisfy $0 budget, modularity, replaceability, and no-AI-dependency constraints simultaneously.

**Decision:** Every external dependency (AI, storage, export, media, queue) sits behind a defined interface ("port"); concrete implementations are "adapters" registered via configuration.

**Why:** A single architectural pattern satisfies modularity, replaceability, and AI-optionality at once — an "unavailable" adapter is a first-class, valid implementation of any port, not an error state.

**Cost Impact:** No direct cost; enables every other cost-saving decision below by making components swappable without rewrites.

**Alternatives Considered:** Direct SDK integration per provider (rejected — creates hard dependencies and rewrite risk on provider change).

**Status:** Accepted.

---

## ADR-002 — Two-Layer Runtime Split (Web / Generation)

**Context:** The site must never go down because AI/generation load is high.

**Decision:** Layer 1 (web: marketing, dashboard, auth) is CDN-served and stateless. Layer 2 (generation: parsing, structuring, export) is a queue-fed worker pool, isolated from Layer 1.

**Why:** Structural guarantee, not a convention — a crash or slowdown in generation cannot propagate to the layer serving SEO/ad-revenue traffic.

**Cost Impact:** Layer 1 stays free (CDN edge caching) at any traffic level; only Layer 2 cost grows with usage, isolating the only real cost driver.

**Alternatives Considered:** Single monolithic app handling both (rejected — couples uptime of cheap, high-value traffic to expensive, variable-load traffic).

**Status:** Accepted.

---

## ADR-003 — Recipe-Based Storage (Not Files)

**Context:** Constitution Principle 4: store recipes, not presentations.

**Decision:** Persistent storage holds structured project data (text, outline, theme) only. Generated PPTX/PDF/DOCX files are temporary, regenerated on demand, auto-deleted after a download window.

**Why:** Decouples storage cost from export volume; a project exported 100 times costs the same to store as one exported once.

**Cost Impact:** Storage cost scales with project count (small, slow-growing), not with export activity (potentially large, fast-growing).

**Alternatives Considered:** Persistent file storage per export (rejected — unbounded storage growth with usage).

**Status:** Accepted.

---

## ADR-004 — Rule-Based Structure Engine as Default, AI as Optional Enhancement

**Context:** Constitution Principles 1–2: software before AI; AI must always be optional.

**Decision:** The Structure Engine's default adapter is rule-based heuristics (heading detection, known narrative shapes). AI, when available, proposes an improved outline on top of the rule-based baseline — never required for a usable result.

**Why:** Makes "AI optional" an enforced architectural behavior (Path A always works, unmodified) rather than a policy statement that could quietly become a hard dependency under feature pressure.

**Cost Impact:** Baseline product has $0 AI cost. AI cost is strictly additive, incurred only when enabled and available.

**Alternatives Considered:** AI-required structuring with rule-based fallback only on failure (rejected — inverts the guarantee; "fallback on failure" is weaker than "baseline that AI enhances").

**Status:** Accepted.

---

## ADR-005 — Data-Driven Template System

**Context:** Design/theming must remain fully rule-based and cheaply extensible.

**Decision:** Layout templates and theme sets are configuration/data (JSON or DB-backed), not hardcoded logic. The Design Engine reads and applies them generically.

**Why:** New templates or themes are added without touching Design Engine code — supports future institutional branding (Premium feature) as a new token set, not a new engine.

**Cost Impact:** Zero runtime cost (deterministic computation, not AI inference).

**Alternatives Considered:** Hardcoded per-template rendering logic (rejected — each new template would require a code change and redeploy).

**Status:** Accepted.

---

## ADR-006 — Managed PostgreSQL From Day One (supersedes original SQLite-first plan)

**Context:** Original blueprint proposed SQLite at launch, migrating to PostgreSQL at scale.

**Decision:** Use free-tier managed PostgreSQL from day one instead.

**Why:** Free-tier managed Postgres costs the same as SQLite ($0) while eliminating a future migration step entirely — a case where the cheapest option and the lowest-future-rework option are the same choice.

**Cost Impact:** $0 at launch, identical to the original plan; avoids migration engineering cost later.

**Alternatives Considered:** SQLite-then-migrate (original plan — superseded, no longer preferred once the $0 managed-Postgres option was identified).

**Status:** Accepted. Supersedes the SQLite-first database decision in the original Technical Blueprint draft.

---

## ADR-007 — Browser-Side Processing, Scoped to Editing/Preview Only

**Context:** Architect review requested browser-side processing as a stronger principle.

**Decision:** Adopted for interactive, low-stakes work (live editing state, theme/layout preview, draft autosave). Explicitly **not** adopted for document parsing or final export rendering.

**Why:** Client-side work is genuinely cheaper and more responsive for editing/preview. Parsing and export are excluded because: (1) parsing is the untrusted-input security boundary and must stay server-controlled per ADR-009; (2) export must render identically across devices, which a mix of client hardware/browsers cannot guarantee.

**Cost Impact:** Reduces server load for interactive features (marginal but real). Does not reduce the dominant cost lines (AI, queue/worker capacity), which remain server-side by design.

**Alternatives Considered:** Full client-side parsing and export (rejected — trades a security guarantee and cross-device consistency for a cost saving on work that is not the dominant cost driver).

**Status:** Accepted, scope-limited as stated.

---

## ADR-008 — AI Roadmap Expanded to Full Constitution Capability Set

**Context:** Original Phase 2 plan sequenced AI Port capabilities to structure-improvement only, deferring rewrite/translate/summarize/suggest.

**Decision:** Phase 2 builds all five capabilities (`propose_structure`, `rewrite`, `translate`, `summarize`, `suggest`) together, each independently null-adaptable.

**Why:** Aligns implementation sequencing with the Constitution's full stated AI scope, per explicit architect decision. Independent null-adaptability per capability means expanding scope doesn't weaken the AI-optional guarantee — each capability degrades individually under load, not all-or-nothing.

**Cost Impact:** Slightly higher Phase 2 build effort (more capabilities implemented at once); no change to baseline runtime cost, since all capabilities remain optional and capacity-checked.

**Alternatives Considered:** Structure-only first, others deferred to a later phase (original plan — superseded per explicit architect decision).

**Status:** Accepted. Supersedes the structure-only Phase 2 scope in the original Technical Blueprint draft.

---

## ADR-009 — Document Parsing Stays Server-Side (Security Boundary)

**Context:** Untrusted uploaded content (documents) must not be able to inject instructions into downstream AI processing.

**Decision:** Parsing happens in a constrained server-side context. The AI Port receives only pre-extracted, pre-sanitized text and performs only narrow, defined operations — never raw file access.

**Why:** Contains prompt-injection risk at the architectural level (the AI Port cannot be reached by untrusted raw content, by construction) rather than relying solely on input filtering, which is a weaker, more error-prone guarantee.

**Cost Impact:** None directly; this is a security decision, not a cost decision. Reinforces the boundary that ADR-007 deliberately declines to move client-side.

**Alternatives Considered:** Client-side parsing (rejected, see ADR-007); filtering-only approach without a hard boundary (rejected — relies on catching every injection pattern rather than making the attack surface structurally unreachable).

**Status:** Accepted.

---

## ADR-010 — Governance: ADR Log and Mandatory Cost-Impact Statements

**Context:** Need a consistent framework so future decisions are checked against documented reasoning, not memory.

**Decision:** (1) This log is maintained going forward for every significant design decision. (2) No new feature is added to the roadmap without an explicit cost-impact statement (infrastructure, AI, storage) in the same why/cost/replaceability format used throughout the Technical Blueprint.

**Why:** Turns the Cost Optimization document from a one-time analysis into a standing checkpoint; turns architectural reasoning into a durable, checkable record instead of something that has to be re-derived or re-argued each time.

**Cost Impact:** No direct cost; process overhead only (writing one ADR entry per significant decision).

**Alternatives Considered:** Relying on the Constitution and Blueprint documents alone without a running decision log (rejected — doesn't capture the *reasoning trail* for decisions made after the original documents, which is exactly where drift happens).

**Status:** Accepted.

---

## ADR-011 — Plugin System

**Context:** The platform is expected to evolve over many years; the plugin surface (AI capabilities, export formats, themes, integrations) will keep growing beyond what's specified today.

**Decision:** Optional capabilities are implemented as plugins. Plugins communicate only through defined Ports. Plugins may be enabled, disabled, or replaced without affecting the core system. Examples: AI, Export, Themes, Templates, Media Providers, Analytics.

**Why:** Strengthens the existing ports/adapters pattern (ADR-001) from "replaceable" to "removable with zero effect on the rest of the application" — a stricter, testable guarantee. Allows OpenPresent to evolve without creating tight coupling as new capabilities are added over time.

**Cost Impact:** None directly. Reduces future maintenance cost by keeping capability growth contained by construction rather than requiring ongoing vigilance.

**Alternatives Considered:** Relying on ports/adapters alone without a named plugin discipline (rejected — "replaceable" doesn't guarantee "removable without side effects"; the stronger guarantee is worth naming explicitly as the plugin surface grows).

**Status:** Accepted. See Technical Blueprint Section 14.

---

## ADR-012 — Cost Ceiling & Circuit Breaker System

**Context:** Founder states plainly: OpenPresent has no budget and no revenue yet, and survival depends on cost control holding automatically at scale, without relying on a solo operator to watch it in real time.

**Decision:** Cost control is implemented as a self-enforcing subsystem, not just a set of design principles: (1) automatic circuit breaker that degrades AI usage in stages when a spend ceiling is crossed, with no manual intervention required; (2) input deduplication/caching for structurally similar submissions; (3) batch inference for queued jobs; (4) preemptible/spot compute for the worker pool, enabled by existing retry/dead-letter handling; (5) cost-per-generation tracked as a continuous, real-time metric feeding the circuit breaker, not just a periodic deployment-stage check.

**Why:** Elevates the founder's stated survival priority from an intention to an enforced architectural property. A solo, $0-budget operator cannot be the real-time safety mechanism — the system has to be incapable of silently overspending while unattended.

**Cost Impact:** No cost itself; exists specifically to bound the cost of everything else with a hard ceiling rather than a best-effort target. Batching and spot compute are expected to materially reduce the AI/worker cost lines identified as the dominant cost driver in the earlier cost board review.

**Alternatives Considered:** Manual monitoring and periodic review only (rejected — insufficient for a solo operator with no budget margin for error; a missed spike could be existential rather than merely costly).

**Status:** Accepted. See Technical Blueprint Section 16.

---

## ADR-013 — AI Adapter Selection Strategy (Confirmed via Phase 2 Implementation)

**Context:** Phase 2 implemented `LocalModelAdapter` (Ollama-compatible HTTP API) alongside the existing `NullAdapter`. Needed to confirm the selection/degradation strategy actually holds under a real failure condition, not just in design.

**Decision:** Adapter selection is config-driven (`OPENPRESENT_AI_ADAPTER` env var), defaulting to `NullAdapter` ($0 cost, no dependency) unless explicitly set to `local_model`. `LocalModelAdapter.is_available()` performs a real health check against the configured model server; every capability method (`propose_structure`, `rewrite`, `translate`, `summarize`, `suggest`) checks availability first and returns the input unmodified — never raises — if the model is unreachable, at capacity, or returns malformed output.

**Why:** This was built and then verified live: with `LocalModelAdapter` configured but no model server actually running (this sandbox has no GPU/model access), `/health` correctly reported `ai_available: false`, and a real document submitted through the full async flow still produced a valid, downloadable presentation via the rule-based fallback — zero errors, zero manual intervention. This confirms Constitution Principle 3 ("AI pauses, generation continues") as an enforced runtime behavior, not just a documented intention.

**Cost Impact:** $0 by default (NullAdapter). Enabling `local_model` costs only local compute/electricity when self-hosted; the adapter never falls back to a paid API automatically — `HostedAPIAdapter` remains a separate, explicitly-configured emergency lever per ADR-004/ADR-006, not something this selection logic reaches for automatically.

**Alternatives Considered:** Defaulting to `local_model` and requiring explicit opt-out (rejected — inverts the safety default; a misconfigured deployment should fail toward zero-cost, not toward assuming AI is available).

**Status:** Accepted. Implementation verified in `backend/adapters/ai/local_model.py` and `tests/contract/test_ai_port.py`.

---

## ADR-014 — Persistence & Ownership Model (Confirmed via Phase 3 Implementation)

**Context:** Phase 3 needed to turn one-off generation into the reusable-project differentiator (Constitution Principle 11) without requiring an account for basic use (core promise: no-account-required, no visible limits).

**Decision:** Storage Port and Auth Port implemented as separate, independent ports. Generation remains fully anonymous-capable via the sync `/generate` endpoint. The async path additionally accepts an optional `Authorization: Bearer <token>` header — if present and valid, the worker persists the result as an owned project (recipe only, per ADR-003); if absent, generation proceeds exactly as before with no project saved. Every Storage Port method is scoped by `owner_id` at the query level, so a project not found and a project owned by someone else return the identical response — no information leak distinguishing the two cases.

**Why:** This was built and then verified live: a real registered user generated a presentation, the worker persisted it as a project tied to that user, `/projects` correctly listed it, and unauthenticated requests to `/projects` were correctly rejected (401) — confirming both halves of the promise (accounts unlock reuse; accounts are never required for generation) hold in running code, not just in the Constitution's wording.

**Cost Impact:** None beyond existing Storage Port cost assumptions (Blueprint Section 3/12) — persistence only occurs for authenticated requests, so anonymous usage (the majority, expected to remain the majority per the "no-account-required" promise) incurs zero additional storage cost.

**Alternatives Considered:** Requiring an account for all generation (rejected — directly contradicts the core promise and the Business Model's stated audience reasoning); storing files instead of recipes on save (rejected — violates ADR-003 and reopens the storage-cost-scales-with-exports problem that recipe-based storage exists to prevent).

**Status:** Accepted. Implementation verified in `backend/ports/storage.py`, `backend/ports/auth.py`, `backend/adapters/storage/sqlite_storage.py`, `backend/adapters/auth/simple_auth.py`, and `tests/contract/test_storage_port.py` / `test_auth_port.py`.

---

## ADR-015 — In-Process Worker for Stage 0-1 Deployment (Corrects Earlier Deployment Guide)

**Context:** The Beginner Deployment Guide originally instructed deploying the worker as a separate Render "Background Worker" service. During actual deployment, the founder discovered Render no longer offers a free tier for that service type — background workers now start at $7/month — while a single free web service remains available. This directly threatened the $0 pre-revenue cost ceiling (Business Model, Section 2).

**Decision:** At Stage 0-1 (Blueprint Section 12), the worker loop runs as a background thread inside the same process as the API, controlled by an `OPENPRESENT_INPROCESS_WORKER` environment variable (default `true`). Only one Render service is needed. A genuinely separate worker process/service is deferred to Stage 2+, switched on by setting the env var to `false` and deploying `backend/workers/generation_worker.py` as its own service once queue depth actually justifies the cost.

**Why:** This is not a workaround bolted onto the architecture — it's what the Blueprint's own staged deployment plan already specified ("single cheap VPS ... for the API" at Stage 0-1, Section 12), which the original deployment guide had drifted from by prematurely splitting into two services. Verified live: with only the API service running (no separate worker command), a submitted job was picked up and completed by the background thread in under 2 seconds, producing a valid downloadable file — confirming the in-process approach works correctly, not just in theory.

**Cost Impact:** Removes the entire second-service cost that would otherwise have broken the $0 pre-revenue ceiling (Business Model, Section 2 / ADR-012's circuit breaker assumption). At Stage 0-1 traffic levels, a single free web service's resources are more than sufficient for both API requests and in-process job processing.

**Alternatives Considered:** Paying $7/month for a separate Render Background Worker (rejected — unnecessary cost at this traffic level, and directly contradicts the $0 pre-revenue ceiling agreed on earlier); moving to a different host entirely to get a free worker tier (rejected — adds migration complexity for a problem the existing architecture already solves cleanly via the Queue Port abstraction).

**Status:** Accepted. Implementation verified in `backend/api/main.py` (`_start_inprocess_worker`, `_in_process_worker_loop`). Deployment guide corrected accordingly — see updated `OpenPresent_Beginner_Deployment_Guide.md`.

---

## ADR-016 — Structure Engine Fix: Thin Content Duplication and Mid-Word Truncation

**Context:** During self-testing before the quiet launch (Roadmap Phase 3's "test it yourself before real students" step working exactly as intended), the founder generated a presentation from a short, single-sentence, unpunctuated input and found it genuinely unusable: a title truncated mid-word ("...21 years old a…"), a second slide duplicating nearly the same full sentence under a fabricated "Key Point 1" label, and a padded "Questions?" closer adding nothing. This is the first real, concrete failure of the core thesis-validation bet from Phase 1 — worth treating seriously rather than patching quietly.

**Decision:** Three fixes to the rule-based Structure Engine: (1) a word-boundary-safe truncation helper (`_smart_truncate`) replacing all raw character-slice truncation, so titles and bullets never cut off mid-word; (2) a content-length threshold (`THIN_CONTENT_WORD_THRESHOLD`, 40 words) below which the engine produces a minimal, honest 2-slide result (title + one "Overview" content slide) instead of forcing the full Title/Key-Point/Questions shape onto content too thin to support it; (3) titles for unpunctuated run-on input are now built via the same word-boundary-safe helper rather than blindly treating the "first sentence" (which, with no punctuation, is the entire input) as quotable title material.

**Why:** The bug wasn't an edge case — short, informal, unpunctuated input (a name, an age, a location, in one breath) is realistic student input, not a pathological test. Producing 3 slides that visibly duplicate the same content and cut off mid-word directly contradicts Constitution Principle 15 ("the rule-based path must be genuinely good on its own") and would have been exactly the kind of first impression that ends a student's use of the product on the first try, per the retention risk flagged throughout the roadmap discussion. Caught during self-testing, before any real student saw it — the "test it yourself first" step (Roadmap Phase 3) did its job.

**Cost Impact:** None — this is a logic fix within the existing rule-based engine, no new dependency, no infrastructure change.

**Alternatives Considered:** Leaving the full padded structure and relying on future AI enhancement (Phase 2's `propose_structure`) to clean up thin-content cases (rejected — directly contradicts the requirement that the rule-based baseline be genuinely good *without* AI, not merely "AI-fixable"); raising the minimum input length required to generate at all (rejected — would turn away real, if short, legitimate student input rather than handling it honestly).

**Status:** Accepted. Fix verified against the real input that surfaced the bug, plus the existing longer-essay test cases (confirmed no regression). Two new regression tests added: `test_thin_unpunctuated_content_produces_no_duplicate_slides`, `test_titles_never_cut_off_mid_word`.

---

## ADR-017 — Structure Engine Fix: Markdown Headers, Instructional Text, Bullet Splitting, False-Positive Headings

**Context:** The founder tested a real resume document (formatted with markdown bold headers, dash separators, bullet lists, and an AI-chat-tool "how to use this" instructional footer — a realistic pattern for content copy-pasted from ChatGPT-style tools) and provided a detailed, specific critique (6.5/10): the title was a full paragraph, an instructional footer was included as if it were content, four consecutive slides were labeled "Overview" with no way to distinguish them, and the closing slide was generic. Direct inspection of the generated file also revealed a second, unreported bug: wrapped lines and bullet items were being joined with no space, producing artifacts like "recordof" and "resourcesto."

**Decision:** Five changes to the rule-based Structure Engine: (1) markdown bold headers (`**SECTION**`) and ALL-CAPS lines are now recognized as headings; (2) a strict word-based heuristic (`_looks_like_title_case_heading`) distinguishes genuine short heading phrases from full prose sentences that merely start with a capital letter, replacing an overly permissive regex that matched both; (3) instructional-footer lines are detected and everything from the first such line onward (within a section, until the next real heading) is excluded from slide content entirely; (4) wrapped prose lines rejoin with spaces while explicit bullet markers (`- `, `* `, numbered) are preserved as distinct items for `_chunk_body` to split on, fixing the word-joining artifacts; (5) a heading with no real body content following it (a false-positive proper noun on its own line, e.g. "Boston University") is merged back into the previous section rather than left as a near-empty phantom slide. Also fixed in the same pass: a legitimately-detected single heading was previously discarded and mislabeled "Overview" because the code treated "one section found" the same as "zero sections found."

**Why:** Every one of these is a realistic input pattern, not a contrived edge case — students copy-pasting AI-generated or markdown-formatted content, résumé-style documents with ALL-CAPS section headers, and wrapped plain-text lines are all ordinary real-world input. This directly serves Constitution Principle 15 ("the rule-based path must be genuinely good on its own") and was caught during the founder's own pre-launch testing (Roadmap Phase 3's "test it yourself first" step), exactly as that step is designed to catch this class of problem before a real student does.

**Cost Impact:** None — logic-only fix within the existing rule-based engine.

**Alternatives Considered:** Relying on future AI enhancement to clean up formatting artifacts (rejected — same reasoning as ADR-016: the rule-based baseline must be good without AI, not merely AI-fixable); requiring users to submit plain, unformatted text only (rejected — unrealistic; real input is messy by default, and handling it is exactly the value the product should provide).

**Status:** Accepted. Verified against a full realistic reconstruction of the resume input across multiple fix iterations (each fix re-tested against the previous ones to confirm no regression). Six new regression tests added: markdown header recognition, prose-vs-heading disambiguation, instructional-footer exclusion, bullet-joining artifact prevention, resume-appropriate closing slide, plus the single-heading-preservation fix. Full suite: 44/44 passing.

---

## ADR-018 — Persistent Storage via Postgres (Fixes Data Loss on Redeploy)

**Context:** The founder reported being unable to log back in after logging out, with a correct "invalid email or password" response. Local testing confirmed the auth logic itself was correct (register → login → login again all worked cleanly within one running process). The actual cause: Render's free web service does not guarantee its local disk persists across restarts or redeploys, and two redeploys had just occurred (the CORS fix and the structure engine fix). Every SQLite-file-backed adapter (Queue, Storage, Auth, Analytics) was silently wiped, deleting the account along with all other data. This is a serious, recurring risk during an active bug-fixing period, not a one-time inconvenience — every future deploy would repeat it.

**Decision:** All four persistence-backed ports now auto-select a Postgres adapter when a `DATABASE_URL` environment variable is present (which Render sets automatically once a Postgres instance is attached to a web service), falling back to the existing SQLite adapters otherwise (unaffected — local dev and this sandbox's tests continue to use SQLite with no change). New adapters: `PostgresAuthAdapter`, `PostgresStorageAdapter`, `PostgresQueueAdapter`, `PostgresAnalyticsAdapter`, each implementing the same Port contract as their SQLite counterpart.

**Why:** This is the deployment finally catching up to what was already decided architecturally in ADR-006 ("Managed PostgreSQL From Day One") — the beginner deployment guide had used SQLite files for practical simplicity, which worked fine for testing but doesn't survive Render's redeploy behavior. Data loss on every code push is unacceptable once real students are involved, and this needed fixing before wider testing, not after. The ports/adapters architecture (ADR-001) is what makes this a contained, low-risk change — four new adapter files and a registry update, zero changes to any API route, engine, or business logic.

**Cost Impact:** $0 — Render's free Postgres tier covers this, with the caveat (already known from earlier research) that free Postgres instances expire after 30 days unless upgraded; worth monitoring as this project continues.

**Alternatives Considered:** Adding a Render persistent disk (rejected — persistent disks are a paid-plan feature, not available on the free web service tier); accepting data loss as a documented limitation of the quiet-launch stage (rejected — unacceptable once real student accounts and saved projects are involved, and the fix cost was low relative to the trust/reliability risk).

**Known limitation, stated plainly:** the Postgres adapters were built carefully against the same contract tests conceptually used for the SQLite adapters, and import/wire correctly, but this sandbox has no real Postgres server to run them against — they are unverified against an actual live Postgres connection. This should be confirmed on first real deployment (see the companion setup guide's checkpoint steps) rather than assumed correct from code review alone.

**Status:** Accepted, pending live verification on first deploy with a real Postgres instance attached.

---

## ADR-019 — Connection Pooling for Postgres Adapters (Fixes "Failed to Fetch" Regression)

**Context:** After ADR-018's Postgres migration was confirmed live (via the `/health` diagnostic fields), the founder reported "Failed to fetch" when trying to register with a real email — a regression of the earlier CORS symptom, but CORS itself was unchanged and already verified working. Root cause: each Postgres adapter held a single, long-lived database connection shared across every caller. The API now serves concurrent web requests (handled in worker threads by Starlette for plain `def` routes) *and* the in-process background worker thread (ADR-015) simultaneously — a raw psycopg2 connection is not safe for concurrent multi-threaded use. Under the wrong timing, this could corrupt connection state mid-request, causing an unhandled failure that skips normal exception handling and CORS header attachment — which a browser reports generically as "Failed to fetch," masking the real cause.

**Decision:** All four Postgres adapters (Auth, Storage, Queue, Analytics) now use a `psycopg2.pool.ThreadedConnectionPool` (min 1, max 5 connections) instead of a single shared connection. Each method borrows a connection for the duration of its operation and returns it immediately after, via try/finally. `PostgresQueueAdapter.dequeue()` — the one method that genuinely needs a real transaction, not just autocommit, for `FOR UPDATE SKIP LOCKED` to provide real protection — explicitly toggles autocommit off for that operation and resets it to on before returning the connection to the pool, so every other method can assume a clean, simple autocommit connection.

**Why:** This is the correct, standard fix for exactly this class of problem — a connection pool is the textbook solution when multiple threads need database access concurrently. It also directly protects the in-process worker design from ADR-015: that decision was made specifically to avoid a paid second Render service, but it necessarily means the worker thread and request-handling threads coexist in one process, which this fix now correctly accounts for.

**Cost Impact:** None — a small in-memory connection pool has negligible overhead at Stage 0-1 traffic levels, and Render's free Postgres tier's own connection limit comfortably accommodates a max-5 pool.

**Alternatives Considered:** Adding a manual `threading.Lock` around each shared connection (rejected — serializes all database access into a single queue, defeating the purpose of concurrent request handling, whereas a pool allows genuine concurrency up to its size); reverting to a genuinely separate worker service to avoid the shared-process threading issue entirely (rejected — reopens the $7/month cost ADR-015 was specifically written to avoid, and doesn't fix the underlying problem, since concurrent web requests alone could already trigger it even without the worker thread).

**Known limitation, stated plainly:** as with ADR-018, this sandbox has no real Postgres server to load-test the pool against directly. The fix is verified as logically correct (imports cleanly, matches the standard psycopg2 pooling pattern, existing test suite unaffected) but not verified under real concurrent load — that verification happens on the next live deployment.

**Status:** Accepted, pending live verification.

---

*Next entry: ADR-020.*
