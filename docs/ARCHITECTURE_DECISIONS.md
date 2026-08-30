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

## ADR-020 — Document Classifier and Type-Specific Recipes (Phase 3.5 Step 2)

**Context:** Reviewer feedback (following the resume-formatting fixes in ADR-017) identified that the Structure Engine treated every document identically regardless of type — "a document splitter, not a presentation generator." The recommendation, echoed independently by two follow-up review documents, was to add rule-based document classification and type-specific "recipes" controlling slide density, closing-slide purpose, and section ordering, without introducing AI dependency.

**Decision:** Added a `DocumentClassifier` (pure keyword-scoring, headings weighted 3x over body-text mentions) that classifies input as `resume`, `academic`, `business`, `lecture`, or `general`. Added a `Recipe` per type controlling: `max_bullets_per_slide` (density), `closing_slide_title` (e.g. "Contact Information" for resumes, "Discussion" for academic papers, "Recommendations" for business, "Summary" for lecture material, vs. the generic "Questions?"), and `canonical_section_order` (e.g. a resume's Experience section is always presented before Education, regardless of the source document's own ordering). The Structure Engine now classifies before structuring and threads the resulting Recipe through every downstream decision.

**Why:** This directly answers the reviewer's core critique — "too much text" and "every slide looks the same" are symptoms of the engine not knowing what kind of document it's building, not the actual root problem. A Recipe fixes density and structure as a natural consequence of knowing the document type, rather than as a separate generic "make it shorter" pass. Fully consistent with Constitution Principle 1 (software before AI) — this required zero AI involvement.

**Bugs found and fixed during testing, not assumed away:** (1) a document whose title has no free-standing intro before its first real section (extremely common — most real documents jump straight from title to "Abstract" or "Executive Summary") was producing an empty "Overview" placeholder slide; fixed by skipping slide generation for a genuinely empty title-section body. (2) A recipe's closing-slide title can collide with a section the source document already has under that exact name (an academic paper's own "Discussion" section duplicating the recipe's "Discussion" closer) — found across all three of the academic, business, and lecture test cases, not an isolated case. Fixed by checking the closing title against every already-generated slide title, not just the last one (the first fix attempt only checked the last slide and still missed a real duplicate that wasn't at the very end).

**Cost Impact:** None — pure logic addition, no new dependency, no infrastructure change.

**Alternatives Considered:** Using AI (`propose_structure`) to determine document type and structure (rejected — the rule-based baseline must remain genuinely good without AI per Constitution Principle 15; classification via keyword scoring is reliable enough for these five categories and keeps the $0-cost guarantee intact for this capability specifically); a single generic "reduce density" pass instead of per-type recipes (rejected per the reviewer's own reasoning — treats the symptom, not the cause).

**Status:** Accepted. Verified against realistic reconstructions of all five document types (resume, academic paper, business report, lecture notes, general/thin content), with actual output inspected before and after each fix, not assumed correct from code review alone. 11 new tests added across `test_document_classifier.py` and `test_structure_port.py`. Full suite: 55/55 passing.

---

## ADR-021 — AI Title Enhancement Wiring (Phase 3.5 Step 3)

**Context:** Since Phase 2 (ADR-008), the AI Port's `rewrite`, `summarize`, and `suggest` capabilities existed as fully-implemented methods with real logic and test coverage, but nothing in `engines/generate.py` actually called them — only `propose_structure` was wired into the pipeline. The review documents' AI strategy (Level 2: "free local AI enhancement") specifically called out title improvement as a concrete example: turning a plain, document-derived title ("The Role of Government in Market Economies") into something presentation-friendly ("Why Markets Need Rules").

**Decision:** `generate_presentation()` now calls `ai.rewrite()` on the title slide's title specifically, when AI is available — deliberately scoped to *only* the title slide, not section headings or recipe-driven closing slides (e.g. "Discussion," "Contact Information" from ADR-020's recipe system), since those are real document structure or deliberate recipe design, not raw text needing improvement. The result is validated (non-empty, under a length cap) before replacing the original; any AI failure, empty response, or absurdly long response silently falls back to the rule-based title with zero visible difference to the caller.

**Why:** This is precisely-scoped, low-risk AI usage — it can only ever improve one specific, cosmetic piece of output, never restructure content, never touch the recipe system's deliberate choices, and never break the pipeline if it misbehaves. Matches Constitution Principle 15 exactly: AI makes a good rule-based result better, and is never required for a usable one.

**Cost Impact:** None beyond what ADR-008/013 already established — this uses the existing `LocalModelAdapter`, no new adapter, no new cost surface. With AI disabled (the default), this code path is a no-op.

**Alternatives Considered:** Also wiring `summarize` for long bullets in the same pass (deferred — kept this step tightly scoped to one clear, testable change rather than bundling multiple AI-enhancement surfaces at once; bullet summarization is a reasonable candidate for a future ADR); rewriting all slide titles including section headings (rejected — headings from real document structure or from ADR-020's recipes are already meaningful and correct; rewriting them risks actively making the output worse, not better).

**Status:** Accepted. Verified via the same FakeHttpClient mock pattern established in ADR-008's tests — no real model server available in this sandbox, so verified as logically correct against a controlled fake response, including a full end-to-end pipeline test producing a valid `.pptx` with the enhanced title. 7 new tests added in `test_title_enhancement.py`. Full suite: 62/62 passing.

---

## ADR-022 — Visual Layout Engine: Statistics and Comparison Layouts (Phase 3.5 Step 4)

**Context:** Review feedback's final quality issue was "no visual intelligence" — every slide rendering as title + bulleted paragraphs regardless of content, even when a slide was clearly a handful of key statistics or a direct comparison. The full recommendation covered eight layout types (Title+points, Comparison, Timeline, Process, Statistics, Quote, Case Study, Summary).

**Decision:** Implemented two layout types for this first version — Statistics and Comparison — rather than the full eight, on the reasoning that two fully-tested, reliably-detected layouts are worth more than eight unreliable ones. A new per-slide `LayoutClassifier` (distinct from ADR-020's per-*document* classifier) detects: **Statistics** — a slide where a clear majority (≥60%) of bullets contain a number/percentage/dollar figure and are short enough to work as a callout; **Comparison** — a slide whose title contains "vs"/"versus". Everything else stays the existing plain bullet-list layout, unchanged. The `Slide` model gained a `layout_type` field, set by the Design Engine (ADR-020's separation of "what content" from "how it looks" — layout classification belongs to Design, not Structure). The PPTX Export adapter now renders three genuinely different shape layouts: statistics as N side-by-side large-text callouts (capped at 4), comparison as two side-by-side text columns, and the original single bulleted placeholder for everything else.

**Why:** This is real visual differentiation without any AI involvement or new dependency — Constitution Principle 1 fully intact. Comparison takes priority over statistics when both could apply (a "2020 vs 2024" slide with stat-heavy bullets is more usefully shown as a comparison than as undifferentiated stat callouts) — a deliberate priority decision, not an accident of code order.

**Verification, not assumption:** every claim here was checked against the actual generated `.pptx` file's shape structure (position, count, non-overlap), not just that the code executed without error — this matters more for a visual/spatial feature than for the earlier text-only fixes, since "it ran successfully" and "it looks right" are further apart here. A business report's stat-heavy "Revenue" section correctly produced three distinct, non-overlapping text boxes at different horizontal positions; a "Renewable vs Fossil Fuels" document correctly produced two side-by-side columns.

**Cost Impact:** None — pure rendering logic, no new dependency (still python-pptx), no infrastructure change.

**Alternatives Considered:** Building all eight layout types from the original recommendation in one pass (rejected — meaningfully higher risk of shipping several half-reliable detectors and renderers instead of a smaller set that's actually solid; Timeline, Process, Quote, and Case Study are reasonable candidates for a future ADR once these two are validated against real usage); using python-pptx's built-in "Comparison" slide layout template instead of manually placed text boxes (rejected — the built-in layout's placeholder structure is less predictable across template variations; manual placement gives full, testable control over exact positioning).

**Status:** Accepted. 8 new tests added in `test_layout_classifier.py`, including two full end-to-end tests that parse the actual exported `.pptx` and assert on real shape geometry. Full suite: 70/70 passing.

---

## ADR-023 — Process/Timeline Layout Added (Extends ADR-022)

**Context:** After ADR-022's Statistics and Comparison layouts were confirmed working, Process/Timeline was the next candidate — unlike Quote or Case Study, it has two reliable structural signals: a title containing "timeline"/"process"/"steps"/etc., or bullets starting with explicit sequential language ("First," "Then," "Step 2").

**Decision:** Added `_is_process_slide` to the Layout Classifier (title keyword match, or ≥2 bullets with a leading sequential marker — same majority-style threshold discipline as the Statistics check, so one incidental "Next" doesn't misfire). Priority order is now: comparison → process → statistics → bullet_list (comparison and process are both more deliberate signals than an incidental cluster of numbers, so they're checked first). The PPTX export adapter renders process slides as numbered step boxes in a row (bold number badge + text beneath, capped at 5 steps), with the sequential marker word stripped from the displayed text since the number badge already conveys order.

**Bug found and fixed during testing, not assumed away:** while verifying process-layout detection with a "Project Timeline" document, the *document* classifier (ADR-020, unrelated to the new layout work) misclassified it as `lecture` — because "week" was in the lecture keyword set and matched the body text ("week one," "week four," etc.), a plausible phrase in any project-planning document, not just lecture material. Same class of over-broad-keyword issue as ADR-017's "conclusion" false positive. Fixed by removing "week" from the lecture keyword set. This was caught specifically because Step 4's testing exercised a document type combination (business/timeline content) that Step 2's own tests hadn't covered — a good example of why testing new features against realistic documents keeps surfacing issues in old ones too.

**Cost Impact:** None — pure logic and rendering addition, no new dependency.

**Alternatives Considered:** Drawing actual connector arrows between step boxes (rejected for this pass — meaningfully more complex positioning/testing for a visual improvement the numbered badges already mostly deliver; worth revisiting later, not now); detecting process slides purely by title keyword without the sequential-language fallback (rejected — would miss documents using clear step language without a "timeline"-style heading, an easy and common real case).

**Status:** Accepted. 5 new tests added, including an end-to-end test verifying real exported shape count/content, and a regression test for the "week" classifier fix. Full suite: 75/75 passing. Quote and Case Study layouts remain explicitly deferred — no reliable rule-based detection signal identified yet for either.

---

## ADR-024 — Real Typography Applied (Fixes "Mediocre Quality" Feedback)

**Context:** After deploying Steps 0-4 (database migration, document classifier/recipes, AI title enhancement, visual layout engine), the founder reported the actual output quality was still mediocre. Direct inspection of a real generated file confirmed the cause precisely: every text run's `font.name` and `font.size` was `None` — only the title's *color* had ever been explicitly set, anywhere in the export code, since Phase 1. `Theme.font_set_id` had existed as a field since the very first version of the Recipe model and was never once read by the export adapter. All the structural and layout work (ADR-020, 022, 023) had been solving a real problem, but the underlying visual design — the thing most directly responsible for "looks professional" — had simply never been built.

**Decision:** Added a `_RenderContext` object bundling the theme's resolved font family and colors, with a single `style_run()` helper applied consistently across every layout renderer (bullet list, statistics, comparison, process) and every text element (titles, body bullets, custom textbox content) — font family, explicit sizing (40pt title slide / 28pt content titles / 18pt body / 16-22pt for specialized layouts), and bold weight where appropriate. Also added a thin accent-colored bar beneath every content slide's title as a visual anchor, using the theme's accent color. Font sets: `Calibri` (sans, for resume/business/general) and `Cambria` (serif, for academic/lecture) — both Office-native fonts, guaranteeing consistent rendering on any real PowerPoint install rather than risking a substituted font.

**A second, related bug found and fixed in the same pass:** theme *selection* (which font/color set gets used) was based on `audience_type.startswith("student")` — a check that was always true for the default caller, meaning literally every document got the same serif "academic" theme regardless of whether it was a resume, business report, or essay. The Document Classifier's output (`outline.document_type`, added in ADR-020) existed and was never actually connected to theme selection either. Fixed: academic/lecture documents get the serif theme; resume/business/general get sans-serif, matching real-world convention instead of one-size-fits-all.

**Why:** This is the direct, concrete fix for the "mediocre quality" feedback — not a structural or content problem, a visual design problem, verified by inspecting real font/size properties before and after (all `None` before; correctly populated and type-appropriate after, confirmed across all five document types).

**Cost Impact:** None — pure rendering logic, no new dependency, no infrastructure change.

**Alternatives Considered:** Using a wider variety of decorative/non-Office fonts for more visual distinctiveness (rejected — risks inconsistent rendering if a viewer's system substitutes an unavailable font; Office-native fonts guarantee the deck looks the same everywhere); per-layout custom font choices instead of one consistent theme font throughout (rejected — inconsistent fonts within one deck reads as more amateurish, not more designed; the whole point of the `_RenderContext` helper is enforcing one consistent identity across every slide).

**Status:** Accepted. Verified against real exported files across all five document types — font family, size, and boldness confirmed populated (not `None`) via direct property inspection, and confirmed to vary appropriately by document type (Calibri vs Cambria). Existing shape-count tests updated to account for the new accent bar shape (a legitimate addition, not a bug) rather than weakening the tests. Full suite: 75/75 passing.

---

## ADR-025 — Tier 1 Visual Polish and Tier 2 Real Image Integration

**Context:** After deploying the Phase 3.5 quality update (ADR-020 through ADR-024), the founder provided two real reference decks as a concrete quality bar. Direct visual inspection (converted to images and viewed, not just structurally parsed) showed both references relied heavily on background color treatments, strong typographic contrast, and — critically — real photographs and custom illustration, none of which OpenPresent's output had. This is split into two tiers: improvements achievable within the existing $0/no-AI-image philosophy (Tier 1), and real image integration (Tier 2), which required examining whether that constraint could be honored while still adding real visual richness.

**Decision — Tier 1 (pure rules, no new dependency):**
- Background color fills per theme (light tinted, not stark white) — `neutral` and `blue_academic` color sets each gained a `background` value.
- Significantly increased typographic size contrast (title slide 40pt → 54pt; content titles 28pt → 40pt; body 18pt → 20pt), matching the boldness observed in both references rather than the previous timid sizing.
- A geometric corner accent (circle) on the title slide only — deliberately not repeated on every slide, to avoid visual monotony from one gimmick stamped everywhere.
- The existing accent bar under content titles (added in ADR-024, then removed for contradicting the pptx design skill's "hallmark of AI-generated slides" guidance, then explicitly restored here per direct founder preference — a deliberate product decision, not an oversight, and documented as such rather than silently reverted).

**Decision — Tier 2 (real image integration, new capability):**
Added a `MediaPort` (parallel structure to `AIPort`: `is_available()` / `search_image(query) -> bytes | None`, never raises, degrades to "no image" on any failure) with two adapters: `NullMediaAdapter` (default, $0, always unavailable) and `UnsplashMediaAdapter` (real stock photography via Unsplash's free Search API, config-driven via `OPENPRESENT_UNSPLASH_ACCESS_KEY`, following the exact same injectable-HTTP-client pattern proven out for `LocalModelAdapter` in Phase 2). The Design Engine assigns a lightweight `image_query` string (not image bytes) to the title slide and the first `bullet_list` content slide — capped at 2 per deck to respect Unsplash's free-tier rate limit (50 requests/hour). The Export adapter fetches the real image fresh at export time and embeds it: title slide gets a right-aligned image; the first eligible content slide splits into left-side bullets (~55% width) / right-side image (~40% width), falling back to the existing full-width text layout with zero visible difference if no image was available or the fetch failed.

**Why stock photos, not AI-generated images:** this is not the same category of dependency the Constitution's "no paid AI dependency" principle was written to prevent — it's real, existing, freely-licensed photography retrieved via a content API, not generated content. It required weighing this distinction deliberately rather than assuming the principle blocked it outright.

**Cost Impact:** Tier 1: none. Tier 2: $0 at the Unsplash free tier, with an explicit, documented constraint — 50 requests/hour is genuinely restrictive at real scale, not just a formality; a caching layer or paid tier becomes necessary once traffic grows meaningfully, which is a known future decision point, not an oversight.

**Honest limitation, stated plainly:** this sandbox has no network access to api.unsplash.com, so `UnsplashMediaAdapter` is verified correct against mocked HTTP responses (12 new tests, including a full end-to-end pipeline test confirming a real image gets embedded as an actual picture shape) — not against the real live API. That verification happens on first deployment with a genuine access key.

**Alternatives Considered:** A keyless image source like Lorem Picsum (rejected — returns random images unrelated to slide content, defeating the purpose); a full dark-theme background redesign matching the references more closely (rejected for this pass — requires overriding text color on every element to maintain contrast on a dark background, meaningfully larger scope and higher risk of a readability bug than the lighter tint approach taken here).

**Status:** Accepted. Tier 1 verified via direct visual inspection (PDF-rendered screenshots), not just code review. Tier 2 verified via mocked HTTP tests plus a real, valid generated image confirming the text+image split layout renders correctly when converted to an actual viewable file. 12 new tests in `test_media_port.py`. Full suite: 87/87 passing.

---

## ADR-026 — P0 Fix: Title/Image Collision Bug (Confirmed via Real Generated Files)

**Context:** After Tier 1+2 went live, the founder reported presentations were "still mediocre." Detailed third-party review of three real generated decks (with real Unsplash images, now confirmed live) identified a severe, confirmed defect: titles and images overlapping on both title slides and content slides, in every deck reviewed. Verified independently before any fix: measured real shape coordinates directly from the uploaded files, confirmed genuine bounding-box overlap (e.g., a content slide's title occupying vertical range [274638, 1417638] EMU, completely contained within the image's range [0, 1920240]), then visually confirmed via rendered images.

**Root causes, both confirmed, not assumed:** (1) the title slide placed an image at a hardcoded position without any check against where the title placeholder — itself at a fixed position from python-pptx's default template — actually sat; the two collided by construction, on every deck, regardless of title length. (2) On content slides, resizing an inherited placeholder's `left`/`width` without also explicitly setting `top`/`height` silently corrupted its position — found serialized as `top=0, height=0` in a real file, causing the title to render literally underneath the image.

**Decision:** Rebuilt both the title slide and the bullet+image content layout to compute all shape positions explicitly from a single shared coordinate scheme (margin/gutter/column-width, the same pattern already proven correct in the Comparison layout), using manually-created textboxes rather than resized inherited placeholders — sidestepping the placeholder-corruption bug entirely, consistent with how every other specialized layout (statistics, comparison, process) already works. **A second bug was found and fixed during verification of the first fix**, not before deploying it: the narrower title column (now sharing space with an image) caused long titles to overflow past the bottom of the slide at a fixed 54pt. Added `_fitting_title_font_size()` — proportional font scaling based on title length and column width, applied to both the title slide and content slide titles, with a readable floor (never below 18pt).

**New automated collision-detection test suite** (`test_layout_collision.py`), directly implementing the critique's own recommendation ("no bad geometry leaves the renderer"): real bounding-box intersection checks between title/body text and images, using genuinely valid generated images (not stubs), covering the exact scenarios that failed (short title, the specific long title from the reported bug, content slides, off-slide-boundary checks). This makes the collision bug class structurally caught by CI going forward, not just fixed once.

**What was deliberately NOT attempted in this pass, stated plainly:** the reviewer's broader recommendation — a full constraint-based layout engine with quality scoring, semantic diagram generation (flow charts for "triangular trade," entanglement diagrams), and content-density-based slide splitting — is a substantially larger undertaking than a bug fix, and was not attempted here. This ADR fixes the P0 defect (bad geometry) specifically. The deeper "turn text into genuinely informative visuals" problem remains open and is the next real product milestone once geometry is trustworthy.

**Cost Impact:** None — pure layout/rendering logic.

**Alternatives Considered:** Using PowerPoint's native autofit (`MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE`) instead of computed font sizes (rejected — LibreOffice's autofit rendering fidelity is inconsistent, and a computed size is deterministic and correct in every renderer, not just PowerPoint itself); patching the specific hardcoded image position that caused the bug rather than restructuring to shared-coordinate manual placement (rejected — would fix the one observed case without addressing the underlying pattern, likely leaving the same class of bug reachable by a different content combination).

**Status:** Accepted. Verified three ways: automated collision tests (5 new, all passing against real generated images), direct visual re-inspection of the exact failing scenario (converted to images, confirmed clean), and the original three uploaded decks' specific failure patterns (long title, content-slide title-under-image) each explicitly covered by a named test. Full suite: 92/92 passing.

---

## ADR-027 — Remove Mid-Sentence Truncation, Raise Image Cap

**Context:** Third-party review of real generated decks (post-collision-fix) flagged sentence truncation with a trailing ellipsis ("achieving $15M in annual synergies within 12…") as the single highest-priority quality defect — it reads as "the generator ran out of space," directly undermining perceived quality regardless of how correct the surrounding layout is. Separately, the founder reported the 2-image-per-deck cap (from ADR-025) felt sparse in real use.

**Decision:** Removed the 140-character hard truncation applied to every bullet (`MAX_BULLET_LENGTH`), replacing it with a much higher safety ceiling (400 characters, `BULLET_SAFETY_CEILING`) that should essentially never trigger for normal prose — bullets now wrap across lines within their text box (`word_wrap = True`, applied consistently including the one native-placeholder path that hadn't set it explicitly) instead of being cut off mid-thought. Raised `MAX_IMAGE_QUERIES_PER_DECK` from 2 to 4, based on real rate-limit math (4 images/deck supports ~12 generations/hour before hitting Unsplash's 50/hour free-tier ceiling — more than sufficient at current pre-launch traffic).

**Why not just raise the character limit instead of removing the cap:** a higher fixed limit still eventually truncates *some* sentence, just less often — it doesn't fix the underlying problem, only makes it rarer and therefore more surprising when it does happen. Letting text wrap naturally (already supported everywhere via `word_wrap`) has no failure mode at all for normal-length sentences.

**Explicitly not addressed by this fix, stated plainly:** the deeper critique — that bullets should be *compressed* into punchier, presentation-appropriate phrasing rather than full sentences wrapped across multiple lines — is a real, separate, much larger problem (requires either AI-based rewriting at scale or a much more sophisticated rule-based compression layer neither of which exist yet). This fix stops the truncation from looking broken; it does not make bullets shorter or punchier. That remains open.

**Cost Impact:** None (truncation fix). Image cap increase: still $0, bounded by the same rate-limit reasoning as ADR-025, just recalculated.

**Status:** Accepted. Verified against the exact sentence pattern flagged in the critique — confirmed rendering in full, no truncation. Full suite: 92/92 passing.

---

## ADR-028 — AI-First Pivot: Topic-First Generation Pipeline + Gemini as Default Hosted Provider

**Context:** OpenPresent through Phase 3 is document-first — a user uploads a document, and AI (when configured) enhances a rule-based structural baseline derived from it. The product direction changed: OpenPresent should be AI-first — a user should be able to type a topic, choose slide count/audience/language, and get a complete, professionally designed deck with no source document at all (spec Section 19, Success Criteria). This is a new capability, not a replacement of the existing document flow, which stays fully intact.

**Decision — new port, not a rewrite of AIPort:** Added `AIPipelinePort` (`backend/ports/ai_pipeline.py`), separate from the existing `AIPort`, with two methods: `generate_presentation_outline(request)` and `review_and_revise(outline, report, request)`. Kept separate from `AIPort` because the capability is genuinely different (generation from nothing vs. enhancement of an existing baseline) — merging them would have forced every `AIPort` implementation (including `NullAdapter`, which must stay a pure pass-through) to grow topic-generation methods that don't fit its contract.

**Decision — Planner/Strategy/Outline/Content collapsed into one AI call:** The spec's conceptual pipeline diagram (Section 3) has Planner, Research, Strategy, Outline Generation, and Slide Content Generation as distinct stages. Implemented as one structured JSON call (`generate_presentation_outline`) rather than five round trips: the Infrastructure Cost Policy (Section 7) explicitly weighs against unnecessary paid/rate-limited API calls, and five sequential round trips would multiply both latency and free-tier quota consumption for no measurable quality benefit over one well-structured prompt asking for the same information. Layout Planning and Image Planning are **not** AI calls at all — per Section 11 ("AI should never directly control formatting"), both remain the existing deterministic `DesignPort`/`RuleBasedDesignAdapter` (layout classifier + image-query derivation), completely unchanged. The seam to split Planner/Research into a genuinely separate call later is a new `AIPipelinePort` method, not a rewrite.

**Decision — Gemini as the default hosted provider, ladder unchanged in shape:** Added `GeminiAdapter`, implementing *both* `AIPort` and `AIPipelinePort` (one provider, two capabilities — real provider independence per Section 6/18: swapping providers later is a new adapter class plus a registry line, not an engines/ or api/ rewrite). Talks to the Gemini REST API (`generateContent`, JSON response mode) over `urllib`, matching `LocalModelAdapter`'s zero-new-dependency discipline. `registry.get_ai_adapter()`'s priority order: (1) `OPENPRESENT_AI_ADAPTER=local_model` — explicit opt-in only, since a hosted Render deployment has no localhost model server; (2) `OPENPRESENT_AI_ADAPTER=gemini`, or auto-selected when `GEMINI_API_KEY` is present — the new hosted default; (3) `NullAdapter` — unchanged $0 fallback. `LocalModelAdapter` was also extended to implement `AIPipelinePort` (shared logic factored into `_JSONPipelineMixin`, `backend/adapters/ai/json_pipeline_base.py`), so local models remain fully first-class for self-hosted/dev use, per the stated provider priority ("local models preferred when available").

**Decision — `is_available()` is a pure config check for Gemini, not a network call:** Unlike `LocalModelAdapter.is_available()` (a cheap localhost ping), a Gemini `is_available()` implemented as a live network call would burn free-tier quota on every `/health` check and every generation attempt. `GeminiAdapter.is_available()` returns `bool(self.api_key)` only; actual reachability failures are caught and degraded at call time, same AI-optional guarantee, without the quota cost.

**Decision — deterministic quality validation runs on every outline, AI review is opt-in:** `backend/validation/quality_validator.py` implements spec Section 13's checks (duplicate slides, excessive bullets, empty sections, repeated bullets, missing closing slide) as pure rules — $0, runs on every generation regardless of which AI adapter (if any) produced the outline, and auto-fixes what it safely can (trimming, deduping, appending a closing slide) without another AI call. The more expensive narrative-level AI revision pass (`review_and_revise`) only fires when `OPENPRESENT_AI_QUALITY_REVIEW=true` **and** the deterministic validator still found unfixed issues — Cost Policy again: don't spend a second model call by default when a $0 pass already resolved the fixable issues.

**Decision — zero-AI fallback for topic mode:** `backend/pipeline/deterministic_topic_outline.py` produces a valid, exportable, generically-structured deck from the topic string alone when no AI pipeline is available or every AI attempt fails — the topic-mode equivalent of `RuleBasedStructureAdapter`, preserving "AI pauses, generation continues" (Constitution Principle 3) for the new flow, not just the original document-upload one. Uses a new `StructureSource.DETERMINISTIC_TOPIC` value (distinct from `RULE_BASED`, which remains document-derived) so analytics can tell the two "no AI" paths apart; a new `AI_GENERATED` value marks a genuine topic-first AI outline, distinct from `AI_ENHANCED` (document baseline touched up by AI).

**New endpoints, existing patterns reused exactly:** `POST /generate/topic` (sync) and `POST /generate/topic/async` + existing `/jobs/{id}` polling (queue job_type `"generate_topic"`, dispatched in `generation_worker.process_one_job` alongside the existing `"generate"` type) — same shape as the document-upload sync/async pair, same anonymous-use-allowed / logged-in-saves-a-project behavior, same Queue/Storage/Auth Ports untouched.

**What was NOT touched:** `backend/engines/generate.py` (document-upload engine), `PptxExportAdapter`, `RuleBasedDesignAdapter`, the Layout Classifier, and every existing Port/adapter for Queue/Storage/Auth/Analytics/Media — all reused as-is by the new topic-first path. This is additive, not a rewrite, per the Existing Code Policy (spec Section 14).

**Cost Impact:** $0 by default (Gemini's free tier; deterministic validator and template fallback add no cost). `OPENPRESENT_AI_QUALITY_REVIEW=true` adds one bounded extra model call per generation, only when needed, opt-in.

**Alternatives Considered:** A single shared `AIPort` covering both enhancement and topic-first generation (rejected — forces every adapter, including the intentionally-inert `NullAdapter`, to implement methods that don't fit its "pure pass-through" contract). Five separate AI calls mirroring the spec's pipeline diagram one stage at a time (rejected on cost grounds — see above; the diagram describes conceptual responsibilities, not a mandate that each become its own network round trip). Making AI own layout/image-query decisions directly (rejected — spec Section 11 is explicit that formatting stays outside AI's control, and the existing deterministic Design Engine already does this reliably).

**Status:** Accepted. 22 new tests (`test_ai_pipeline_port.py`, `test_quality_validator.py`, `test_ai_generate_engine.py`) covering: Gemini availability-without-network-call, structured-JSON parsing (including malformed/wrong-slide-count/blocked-response/markdown-fenced cases), `LocalModelAdapter`'s new pipeline capability, every quality-validator rule, and the engine's fallback-to-deterministic behavior end-to-end (a real `.pptx` byte stream, confirmed non-empty, produced with zero AI configured). Full suite: 114/114 passing.

## ADR-029 — Multi-Provider Image System: Relevance Scoring, Caching, Duplicate Prevention, Quota-Based Fallback

**Context:** The image system through Phase 4/ADR-028 had one provider (Unsplash), an artificial deck-level cap of 4 images (because a single provider with a 50 req/hr free tier had no fallback if exhausted), and "take whichever result comes back first" as the entire relevance strategy. Spec Section 8 calls for caching, duplicate prevention, provider quotas, fallback providers, relevance scoring, and attribution handling; Section 9 calls for Unsplash/Pexels/Pixabay/Wikimedia Commons as pluggable providers. None of this existed.

**Decision — two-phase provider interface (discover, then fetch):** Each provider adapter (`UnsplashProvider`, `PexelsProvider`, `PixabayProvider`, `WikimediaProvider`, all in `backend/adapters/media/`) implements `search_candidates()` (cheap — metadata only) separately from `fetch_bytes()` (only called once, for the single winning candidate, after scoring and dedup). This avoids downloading image bytes for the N-1 candidates that don't get used — real bandwidth savings once relevance scoring means comparing 15-20 candidates across providers per slide instead of accepting provider #1's top hit blindly.

**Decision — relevance scoring is a free heuristic, not a real ML capability:** `backend/adapters/media/relevance.py`'s `score_relevance()` is Jaccard-style token overlap between the search query and whatever text metadata a provider returns (description/alt-text/tags). This is honestly a coarse proxy — there's no $0 way to do real image-relevance scoring without a paid vision API, which the Infrastructure Cost Policy (Section 7) rules out. Documented as a heuristic rather than oversold; still strictly better than the previous "take the first result" behavior.

**Decision — caching stores candidate metadata, never image bytes:** `CandidateCache` is in-process, in-memory, TTL'd (1 hour), keyed by normalized query. What's cached is provider/id/description/score — never the actual image bytes, which are still fetched fresh from the provider's URL every time a candidate is chosen. This is deliberately consistent with the existing "no large media database" principle (Blueprint Section 3.7/9): the cache reduces redundant provider *search* calls within one process's lifetime, it does not become a persistent media store.

**Decision — duplicate prevention via exclude_ids, not a global blocklist:** `MediaPort.search_image(query, exclude_ids=...)` — the exporter (`PptxExportAdapter`) now tracks `used_image_ids` across one deck's export in `_RenderContext` and passes it on every subsequent image request, so the router picks the next-best scored candidate instead of the same photo appearing twice in one presentation. Scoped to a single deck's export, not cross-deck (a photo can legitimately appear in two different presentations — only within-deck repetition is the actual problem being solved).

**Decision — provider quotas + automatic fallback, not a hard-fail:** `QuotaTracker` is a simple in-process fixed-hour-window counter per provider (Unsplash 50/hr, Pexels 200/hr, Pixabay 5000/hr, Wikimedia self-imposed 100/hr as a courtesy — no hard limit is documented for Commons at this usage level). `MultiProviderMediaAdapter` queries providers in priority order — Unsplash, Pexels, Pixabay, Wikimedia — skipping any that are unconfigured or quota-exhausted, continuing to collect candidates until it has enough or runs out of providers. Wikimedia requires no API key at all, making it a genuine universal fallback: a deployment with zero image API keys configured still has a working (if lower-quality-metadata) image system.

**Decision — the deck-level image cap is removed, not raised:** The old `MAX_IMAGE_QUERIES_PER_DECK=4` constant in `RuleBasedDesignAdapter` is gone. It existed only to protect a single provider's low quota; now that quota protection lives correctly in the Media layer (per-provider, with fallback), an artificial deck-level cap on top of that is redundant and was capping decks below what the real, now much higher, combined quota allows. Every eligible slide gets an `image_query`; whether it actually gets an image depends on real provider availability at export time.

**Decision — attribution handling, only where required:** `ImageResult.attribution` is set by providers whose license requires visible credit (Wikimedia Commons always sets it; Unsplash/Pexels/Pixabay set `None` since their free-use terms don't require an on-slide credit, though Pexels/Pixabay still populate a courtesy attribution string that the renderer chooses not to force onto every slide). `PptxExportAdapter._add_attribution_caption()` renders a small caption beneath the image only when `attribution` is set.

**Bug found and fixed in the same pass (not scoped originally, but directly adjacent code):** `PptxExportAdapter` was including `BlockType.NOTE` text in the visible slide body alongside bullets — speaker notes were rendering as visible content on every slide instead of going into PowerPoint's actual notes pane (`slide.notes_slide`). Fixed as part of this ADR since the notes-bundling work (ADR-030) made the bug impossible to ignore — a separate speaker-notes DOCX export would have been shipping alongside notes that were *also* still wrongly visible on-slide.

**Alternatives Considered:** A single "best" provider with more generous paid tier (rejected — Cost Policy). Real ML-based image relevance via a vision API (rejected — cost). Persisting fetched images to reduce repeat downloads across different decks (rejected — violates the "no large media database" principle; the metadata-only cache captures the real repeat-cost savings without that tradeoff).

**Status:** Accepted. New tests: `test_media_port.py` (rewritten for the two-phase contract, including an end-to-end dedup test through the real export pipeline), `test_multi_provider_router.py` (11 tests: scoring, caching, dedup, provider fallback, quota, never-raises).

---

## ADR-030 — Proper Multi-Stage AI Pipeline, AI-Driven Layout Planning, Additional Providers, Research Stage, Presentation Variety, Real Quality Review, DOCX Speaker Notes, Sentry Monitoring

**Context:** ADR-028 shipped a deliberately minimal AI-first MVP: one hosted provider (Gemini), Planner/Strategy/Outline/Content collapsed into a single AI call for cost reasons, layout/image-query assignment kept fully rule-based ("AI should never directly control formatting"), quality review's AI-assisted pass opt-in and off by default, and no research, variety, monitoring, or notes-export capability at all. Explicit product direction reversed several of these scoping decisions. This ADR documents the reversal and the resulting architecture — the biggest single revision to the AI pipeline since ADR-028 introduced it.

**Decision — five real stages, five real (potential) AI calls, not one:** `AIPipelinePort` (`backend/ports/ai_pipeline.py`) now has `generate_strategy` → `generate_outline_structure` → `generate_slide_content` → `plan_layout` → `review_and_revise`, each with its own prompt and its own strict JSON parser in the shared `_JSONPipelineMixin` (`backend/adapters/ai/json_pipeline_base.py`). This directly supersedes ADR-028's cost-driven single-call design. One deliberate batching choice remains: slide *content* generation is still one call across all slides in an outline, not one call per slide — N per-slide calls would multiply latency for a batch of short, interdependent outputs that one well-structured prompt handles equally well; this is clearly a different, narrower tradeoff than the old "merge everything" approach, not a reversion to it.

**Decision — AI now plans layout, per explicit product direction, with the rule-based classifier retained as the deterministic fallback:** `plan_layout()` gives the AI the actual generated slide content and asks it to choose `layout_type` (from the four the renderer supports: bullet_list/statistics/comparison/process) and `image_query` per slide. This reverses ADR-028's "AI should never directly control formatting" stance — but the reversal is scoped: `DesignPort.apply_theme()` gained an `ai_layout_planned: bool` parameter (default `False`), and `RuleBasedDesignAdapter`'s existing regex-based `classify_layout()` remains fully intact as what runs when `ai_layout_planned=False` — i.e., whenever the AI pipeline is unavailable or any stage failed. The Constitution guarantee (AI is a quality upgrade layered on a fully-functional deterministic path, never a hard dependency) is preserved; what changed is which layer AI is allowed to influence, not whether a no-AI path still produces a complete deck.

**Decision — additional AI providers via a shared OpenAI-compatible base, cascading composite fallback:** Groq and OpenRouter both expose an OpenAI-compatible `/chat/completions` endpoint, covered by one shared `_OpenAICompatibleBase` (`backend/adapters/ai/openai_compatible_base.py`); HuggingFace's Inference Providers router is the same shape, so it reuses the identical base. `CompositeAIAdapter` (`backend/adapters/ai/composite_adapter.py`) wraps every provider with credentials configured, in priority order (local model → Gemini → Groq → OpenRouter → HuggingFace), and cascades through them per pipeline-stage call: a stage failing on one provider (network error, malformed JSON, outage, quota exhaustion) tries the next configured provider before the whole AI attempt is abandoned. This is the concrete difference from ADR-028, where a Gemini failure dropped straight to the deterministic template — now it fails over across every configured provider first. `registry.get_ai_adapter()` auto-builds this composite from whatever `*_API_KEY` env vars are present; `OPENPRESENT_AI_ADAPTER=<name>` still forces a single provider for testing/debugging.

**Decision — Research/Knowledge Expansion is real but conservatively scoped:** `ResearchPort` (`backend/ports/research.py`) feeds an optional `ResearchBrief` (facts + sources) into the Strategy stage. `DuckDuckGoResearchAdapter` scrapes DuckDuckGo's lite HTML results — free, no API key — but is explicitly documented as best-effort/lower-reliability than a real search API would be, and is **disabled by default** (`OPENPRESENT_RESEARCH_ADAPTER=duckduckgo` to opt in); `NullResearchAdapter` is the default, matching every other optional-capability port's pattern in this codebase. Every failure mode degrades to an empty brief, never blocks generation.

**Decision — presentation variety is AI-in-the-loop for narrative structure, genuinely random for visual theme:** `backend/pipeline/variety.py` catalogs six narrative styles (Classic Narrative, Problem-Solution, Story-Driven, Data-Driven, Chronological, Comparative). The Strategy stage prompt includes a *randomly suggested* starting candidate but is explicitly told it can override it if the topic fits a different style better — deliberately not pure random selection, since a badly-mismatched random style (e.g. "Chronological" forced onto a deck with no timeline) would violate the Quality Philosophy (spec Section 1: quality always wins over variety-for-its-own-sake). Visual theme variety (`pick_theme_variant()`) *is* genuinely random, since a color/font variant carries no topic-fit risk the way narrative structure does. **Bug caught during this work:** the engine's first attempt at theme variety constructed `Theme(color_set_id=X)` with every other field left at its dataclass default, which `RuleBasedDesignAdapter.apply_theme()` silently ignored — it only respects an explicit theme when `layout_template_id != "default"`, so the override never took effect. Fixed via a new `get_theme_variant()` helper that returns a fully-resolved `Theme`, with a regression test (`test_engine_theme_variety_actually_takes_effect`) added specifically to catch this class of bug reappearing.

**Decision — quality review, built out properly, and no longer opt-in:** `backend/validation/quality_validator.py` gained the two checks ADR-028 explicitly deferred as "too hard to detect reliably with rules" — inconsistent terminology (surface-form variants of the same normalized term, e.g. "AI"/"Ai"/"A.I.") and poor hierarchy (paragraph-length bullets) — plus a new overflow-risk heuristic (a rough per-layout-type character budget, not a measurement of actual rendered extent; the renderer's own font-fitting logic still has final say). None of these three auto-fix — they're flagged for the AI revision pass or a human to judge, since an automated rewrite risking a false positive is worse than a flagged-but-unfixed true positive here. The AI-assisted `review_and_revise` pass now runs whenever real issues remain after the deterministic pass, by default — no longer gated behind `OPENPRESENT_AI_QUALITY_REVIEW`, which is removed.

**Decision — PPTX export bundled with a separate speaker-notes DOCX by default:** `SpeakerNotesDocxExportAdapter` (`backend/adapters/export/docx_notes_adapter.py`) produces a Word document listing every slide's title, on-slide bullets, and speaker notes. `backend/engines/export_bundle.py` zips it together with the primary export. Both `/generate` and `/generate/topic` (sync and async, including the worker's job-result path) now return `presentation.zip` by default; `bundle_speaker_notes=false` opts back into a single bare file for programmatic callers. This is a direct, explicit product request, and also closes a real gap the ADR-029 notes-rendering-bug fix exposed: without a place for notes to actually live outside the slide body, there was no way to consume them at all pre-fix.

**Decision — Sentry, wired at the boundaries the spec names, structurally independent of business logic:** `backend/monitoring/sentry_setup.py` is a no-op whenever `sentry-sdk` isn't installed or `SENTRY_DSN` isn't set — every call site in `engines/`, `adapters/media/`, and `workers/` calls `capture_exception`/`add_breadcrumb` unconditionally, so nothing in business logic needs to know or care whether monitoring is actually active. Wired at exactly the boundaries spec Section 16 names: AI provider failures (per-stage, inside `_run_ai_pipeline`), image provider failures (inside `MultiProviderMediaAdapter._discover_candidates`), rendering/export failures (`generate.py`, `ai_generate.py`), and worker-level unexpected exceptions.

**What was NOT touched:** The document-upload engine (`generate.py`) still uses the original single-stage `AIPort.propose_structure()` enhancement path — this ADR's multi-stage pipeline is specific to topic-first generation (`AIPipelinePort`), a deliberately separate capability from ADR-028 that remains separate here. `PptxExportAdapter`'s core rendering logic (four layout types, font-fitting, collision-safe geometry from ADR-026) is unchanged except for the notes-bug fix and attribution captions (ADR-029).

**Cost Impact:** Up to 5-6 AI calls per topic-first generation now (vs. 1-2 previously) — a real cost increase, accepted per explicit product direction over the prior cost-minimizing design. Partially offset by: quality review only firing when real issues remain (not every generation), and the composite provider cascade meaning a single provider's rate limit is less likely to force a fallback to the fully-deterministic (and lower-quality) path.

**Status:** Accepted. New/updated tests: `test_ai_pipeline_port.py` (rewritten, 21 tests covering all 5 stages across Gemini/local-model/Groq plus composite cascading), `test_quality_validator.py` (updated for the 3 new checks), `test_ai_generate_engine.py` (expanded with full-pipeline end-to-end tests plus the theme-variety regression test), `test_research_port.py`, `test_sentry_monitoring.py`, `test_export_bundle.py`. Full suite: 154/154 passing.

## ADR-031 — Production Hardening: Tolerant Parsing, Scaled Token/Timeout Budgets, Bugsink Monitoring

**Context:** Live deployment of the ADR-030 pipeline surfaced three distinct, real production failures in quick succession, each diagnosed from actual Render logs after the logging gap below was fixed. All three shared a root shape: a strict assumption (exact count, fixed timeout, fixed token limit) that held for a small/simple case and silently broke for a larger/more realistic one — a `>3 slides falls back to the deterministic template` bug report, traced through to three separate causes.

**Bug 1 — invisible failures.** `capture_exception`/`add_breadcrumb`/`capture_message` only sent to Sentry — when Sentry's SaaS became unreachable from the deployer's network (a genuine, unrelated regional access issue), every AI pipeline failure was silently swallowed with zero visibility anywhere, including Render's own Logs tab. **Fix:** every one of these functions now always logs to stdout via Python's standard `logging` module first, unconditionally, with Sentry (or whatever `SENTRY_DSN` points at) as an additive layer on top, never a replacement. This is what actually made bugs 2 and 3 diagnosable at all.

**Bug 2 — Stage 4 (layout planning) off-by-one.** The prompt said "for every slide except the title slide" and asked for `N-1` entries; models don't reliably follow "skip the first item" instructions and returned `N` instead, and the old strict-equality parser discarded the entire AI attempt over the single extra entry. **Fix:** reworded the prompt to ask for one entry per slide including the title slide (removing the ambiguous instruction at the source), and made `_parse_layout_json` tolerant of count mismatches — extra entries are dropped, missing ones leave that slide at a safe default (`bullet_list`, no image) rather than discarding the whole response.

**Bug 3 — Stage 2 (outline structure) off-by-one.** Same failure shape, different stage: "Slide 1 is the title slide. The last slide must close the presentation" was read by models as *additional* slides beyond the requested count (consistently `N+1`, confirmed in production logs as 15→16 and 10→11). **Fix:** reworded the prompt to state explicitly that the title and closing slides count *within* the total ("Generate EXACTLY N slides TOTAL — not N plus a title slide, not N plus a closing slide"), and made `_parse_structure_json` tolerant (~15% or minimum-2 tolerance): extra items truncated, a slightly-short response accepted as-is since every downstream stage already keys off the actual returned count (`len(structure)`), not the original request. A response far outside tolerance still correctly raises.

**Bug 4 — token/timeout budgets not scaled.** No AI adapter set an explicit output-token limit, so each provider's own default silently truncated the JSON response once slide count grew past a handful — invisible for 3 slides, broken for 10+. Fixed by scaling `max_tokens` with slide count (`_token_budget()`). This fix then directly caused **Bug 5**: a bigger token budget takes proportionally longer to generate, and the read timeout stayed fixed at 45s, cutting off still-in-progress larger responses. Fixed by scaling the timeout the same way, from the same slide-count input (`_read_timeout()`), so the two can't drift out of proportion again. Both fixes applied identically across all 5 AI providers (Gemini, Groq, OpenRouter, HuggingFace, local models) via the shared `_JSONPipelineMixin`.

**Decision — switched primary error-monitoring backend from Sentry SaaS to Bugsink.** Sentry's hosted dashboard became unreachable from the deployer's network (unrelated to this codebase). Rather than build Sentry-specific integration, the existing `sentry-sdk` package already speaks the standard Sentry ingestion protocol, which Bugsink (and GlitchTip, and self-hosted Sentry) implement — switching backends is a `SENTRY_DSN` value change, zero code changes. Bugsink specifically chosen for a higher hosted event quota at its price point and a lighter footprint (SQLite, no Redis/Celery) than GlitchTip's Postgres+Redis self-host requirement — though the code works identically with any of them. `SENTRY_TRACES_SAMPLE_RATE=0` is recommended for Bugsink specifically since it doesn't process performance-tracing data.

**Also:** added a trivial `GET /` route — Render's own infrastructure probes the bare root path by default, which had no handler and was logging as a 404 (cosmetically confusing, not an actual problem); now returns a simple 200.

**Status:** Accepted. Every fix reproduced the exact production failure locally before and after the change (e.g. `structure_json(11)` against a 10-slide request, matching the real "10 requested, got 11" log line verbatim) rather than relying only on synthetic test cases. 20 new regression tests added across the layout, structure-count, and token/timeout-scaling fixes.

---

## ADR-032 — Multi-Provider Research: Merged Grounding, Real APIs Replace Scraping as the Default

**Context:** ADR-030's Research stage shipped with exactly one provider (`DuckDuckGoResearchAdapter`, HTML-scraping `lite.duckduckgo.com`), explicitly documented as best-effort and disabled by default specifically because of that fragility. Product direction: replace it with something more reliable, and build a fallback system so generation draws on "the best data and facts," not a single scraped source.

**Decision — merge facts from multiple providers, don't just fail over.** Every other multi-provider system in this codebase (`CompositeAIAdapter` for AI, `MultiProviderMediaAdapter` for images) uses a "first one that works wins" strategy, because those capabilities produce one output where redundancy doesn't compound (one outline, one embedded photo). Research is different: a Tavily result and a Wikipedia result about the same topic are genuinely complementary — one reflects the current web, the other is encyclopedic and authoritative — and combining them produces richer grounding for the Strategy stage than either alone. `CompositeResearchAdapter` (`backend/adapters/research/composite_research.py`) queries multiple available providers (bounded: `MAX_PROVIDERS_QUERIED=3`, `MAX_TOTAL_FACTS=10`, to keep this from uncontrollably adding latency on top of an already multi-call pipeline) and merges their facts, deduplicated by normalized text.

**Decision — Wikipedia (real REST API) replaces DuckDuckGo scraping as the default free tier, on by default.** `WikipediaResearchAdapter` uses Wikipedia's actual documented, stable MediaWiki search + REST summary APIs — not HTML scraping — playing the same "always-configured, no-key, genuinely reliable" role `WikimediaProvider` already plays for images. Because it's materially more reliable than what it replaces, Research is now **on by default** (`registry.get_research_adapter()` returns a live `CompositeResearchAdapter`, not `NullResearchAdapter`, when nothing is explicitly configured) — a real behavior change from ADR-030's opt-in default, justified specifically because the reliability concern that motivated making it opt-in no longer applies to the new default provider. `OPENPRESENT_RESEARCH_ADAPTER=null` remains available to fully disable it, consistent with every other capability's rollback pattern (DEPLOYMENT.md).

**Decision — Tavily and Brave as higher-priority, keyed providers.** `TavilyResearchAdapter` (`TAVILY_API_KEY`) is ranked first when configured: Tavily is purpose-built for LLM-grounding use cases specifically (returns a synthesized answer plus source snippets shaped for exactly this pipeline stage, not general web results repurposed for it), with a real free tier. `BraveSearchResearchAdapter` (`BRAVE_SEARCH_API_KEY`) ranks second — an independent live web index, valuable for currency Wikipedia can't provide for very recent topics. Both optional; the composite works correctly with zero, one, or all three configured.

**Decision — DuckDuckGo scraping demoted, not deleted.** Still available via `OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH=true` as an extra free bonus source, but no longer included in the default composite and no longer the primary free/no-key option — that role now belongs to Wikipedia's real API. Kept rather than removed because it still adds marginal value when explicitly opted into, and removing working code without a functional reason would violate the Existing Code Policy for no benefit.

**Cost impact:** $0 with zero keys configured (Wikipedia only). Tavily and Brave both have real free tiers; exceeding them degrades that one provider's contribution, not the whole Research stage (each provider call is independently wrapped in try/except inside the composite). Research now runs by default where it didn't before, adding 1-3 additional network calls (sequential, bounded by `MAX_PROVIDERS_QUERIED`) ahead of the Strategy stage — a real, deliberate latency/cost tradeoff for grounding quality, consistent with ADR-030's already-accepted "more calls for more quality" direction.

**Status:** Accepted. 27 new tests across all four provider adapters (including empty/broken-client/malformed-response cases) and the composite's merge/dedup/cap/skip/never-raises behavior. Also fixed a hermeticity gap caught while adding these: two existing engine tests didn't mock the research adapter and would have made live Wikipedia network calls during test runs in any environment with real network access — this sandbox's network restrictions happened to fail fast rather than hang, which is what let it go unnoticed; the shared test fixture now mocks research by default for every test in that file. Full suite: 193/193 passing.

## ADR-033 — AIPort Invisible Failures and Missing Cascade Fixed (Document-Upload Flow)

**Context:** Product report: "upload a document" generations still looked purely rule-based despite `/health` confirming 4 AI providers fully configured and available — the exact same symptom class ADR-031 diagnosed and fixed for the topic-first pipeline, but in the *other* AI code path (`AIPort`, used by `backend/engines/generate.py`'s document-upload enhancement), which never received either of ADR-031's two fixes.

**Bug 1 — invisible failures, again.** Every one of `AIPort`'s five methods (`propose_structure`, `rewrite`, `translate`, `summarize`, `suggest`), across all three adapter implementations (`GeminiAdapter`, `LocalModelAdapter`, `_OpenAICompatibleBase` shared by Groq/OpenRouter/HuggingFace — 15 methods total), caught every exception with a bare `except Exception: return <original unmodified input>` and zero logging. A failing Gemini call for `propose_structure` was completely indistinguishable from a successful one that happened to return the input unchanged. **Fix:** every one of these 15 call sites now calls `capture_exception` (tagged `stage=ai_port`, `method=<name>`, `provider=<adapter>`) before degrading — same fix shape as ADR-031's Bug 1, applied to the code path that was missed the first time.

**Bug 2 — no cascading, ever, for these methods.** `CompositeAIAdapter`'s original design (ADR-030) delegated `AIPort` methods to the *first available* provider only, with the stated reasoning that "these methods already self-degrade internally, so cross-provider cascading adds complexity without much benefit." In production this reasoning was proven wrong: if the first configured provider's `propose_structure` call failed for any reason, the document-upload flow silently produced **zero** AI enhancement — every upload rendered as the untouched rule-based baseline — even with 3 other fully-capable, fully-configured providers sitting unused. The root problem with the original design: because each adapter's public method already swallowed its own exceptions and returned the unmodified input, the composite had no way to tell "provider failed" apart from "provider succeeded but chose not to change anything" — there was nothing to cascade *on*.

**Decision — split each capability into a raising core and a safe public wrapper.** New `_TextEnhancementMixin` (`backend/adapters/ai/json_pipeline_base.py`), mixed into all three adapters alongside the existing `_JSONPipelineMixin`, provides `_propose_structure_raising`, `_rewrite_raising`, `_translate_raising`, `_summarize_raising`, `_suggest_raising` — the actual prompt-building and parsing logic, which now genuinely raises on any failure (malformed response, empty result, network error) instead of swallowing it. Each adapter implements one new primitive, `_call_text(self, prompt: str) -> str` (plain-text, non-JSON-mode — a one-line delegation to the adapter's existing internal call method, e.g. `self._generate_text(prompt)` for Gemini). Each adapter's existing PUBLIC method (`propose_structure`, etc.) becomes a thin wrapper: call the `_raising` version, catch, log via `capture_exception`, degrade to the original input — this is unchanged, correct behavior for standalone (single-adapter, non-composite) use. `CompositeAIAdapter` now calls the `_raising` methods **directly**, cascading through every configured provider itself and only falling back to the original input after all of them have been tried and failed (`_cascade_text`, mirroring the existing `_cascade` used for `AIPipelinePort` stages).

**Net effect:** a Gemini failure on `propose_structure` now genuinely falls through to Groq, then OpenRouter, then HuggingFace, before the document-upload flow gives up and keeps the rule-based baseline — matching the reliability model the topic-first pipeline has had since ADR-030, now applied consistently to both AI code paths in this codebase.

**Status:** Accepted. 8 new regression tests: cascading success (provider 1 fails, provider 2 succeeds) and full-degrade (every provider fails, safe fallback, never raises) for `propose_structure`, `rewrite`, `summarize`, and `suggest`; plus 2 tests confirming the logging fix actually fires `capture_exception` with the correct tags on a real failure. All 9 pre-existing `test_ai_port.py` tests (standalone safe-degrade behavior) still pass unmodified, confirming the refactor didn't change single-adapter behavior. Full suite: 201/201 passing.

## ADR-034 — Four Real Provider Failures Diagnosed Live, Document-Upload Controls Completed

**Context:** ADR-033's logging fix worked exactly as designed — the very next production log showed complete, individually-diagnosable tracebacks for all 4 configured AI providers failing on the document-upload flow, instead of the prior total silence. Each failure turned out to be a distinct, real, fixable cause — none of them a repeat of the architectural bugs already fixed. Separately, document-upload was missing user-facing controls (audience, language, slide count) that topic-first generation already had.

**Bug 1 — Gemini 404, model retired.** `models/gemini-2.0-flash` was fully shut down by Google on June 1, 2026 (confirmed via Google's own deprecation notice, which explicitly warns hardcoded model IDs are a real liability, not theoretical). **Fix:** `DEFAULT_MODEL` updated to `gemini-3.5-flash`. Still just a config value (`OPENPRESENT_GEMINI_MODEL`) — this is the second time this exact default has needed updating, underscoring that periodic re-verification against `ai.google.dev/gemini-api/docs/deprecations` is a real operational task for this codebase, not a one-time setup step.

**Bug 2 — Groq 403/error-1010, Cloudflare bot block.** Confirmed via Groq's own community forum: Cloudflare's Bot Management (sitting in front of Groq's API) blocks Python's default `urllib` User-Agent string (`Python-urllib/x.y`) outright, before the request ever reaches Groq's own API logic — completely unrelated to the API key or account. **Fix:** every outbound HTTP call this codebase makes (`backend/adapters/http_headers.py`, `with_user_agent()`) now sends a real, honest User-Agent (`OpenPresent/1.0 (+repo-url)`). Applied everywhere, not just Groq — the same Cloudflare-fingerprinting risk applies to any provider behind it (Unsplash, Pexels, Tavily, Brave, etc.), and there's no downside to identifying honestly.

**Bug 3 — OpenRouter 404, free slug delisted.** The hardcoded `meta-llama/llama-3.1-8b-instruct:free` slug returned "unavailable for free... use the paid version." Live research confirmed this isn't a one-off: OpenRouter's free-tier roster is documented churning within days-to-weeks in mid-2026, with entire free model families delisted inside a single week on at least one occasion. **Decision:** rather than pick another specific slug (which the evidence says will likely also break soon), switched `DEFAULT_MODEL` to `openrouter/free` — OpenRouter's own auto-router alias, purpose-built by OpenRouter specifically to survive this churn by dynamically selecting from whatever's currently free and available. This is a materially different fix strategy than Bug 1's (pick a new fixed value) — deliberately so, since OpenRouter's free tier has a qualitatively higher churn rate than Gemini's model catalog.

**Bug 4 — HuggingFace "could not be parsed," JSON mode never requested.** The call succeeded — no HTTP error — but `_propose_structure_raising` was calling `_call_text(prompt)` without ever requesting structured output, relying purely on the prompt's own wording ("Respond ONLY with valid JSON") to get parseable output. HuggingFace's router didn't reliably comply with that alone. **Fix:** `_call_text` now accepts a `json_mode` flag, threaded from `_propose_structure_raising` (the one `_TextEnhancementMixin` method that genuinely needs structured output — the other four correctly stay plain-text). Implemented consistently across Gemini (`responseMimeType`), the OpenAI-compatible base used by Groq/OpenRouter/HuggingFace (`response_format`), and local models (Ollama's own `format: json` option) — not just the one provider that happened to surface the bug first.

**Decision — document-upload flow gets the same controls topic-first generation already had.** `audience_type`, `language`, and a new `target_slide_count` are now real parameters on `/generate` and `/generate/async` (previously `generate_presentation()` already supported `audience_type`/`language` internally, but the API layer never exposed either). `target_slide_count` is a soft hint threaded into `propose_structure`'s prompt (`AIPort.propose_structure` gained an optional parameter, implemented identically across all adapters and `CompositeAIAdapter`'s cascade) — the document flow's rule-based structure engine has no native "target count" concept (it derives structure from the document's own sections), so this only takes effect when AI enhancement succeeds; the rule-based baseline always renders at whatever count it naturally produces regardless.

**Decision — `language` now actually translates content.** Found while wiring up the exposure: `language` was already a parameter on the engine, but only ever stored as Recipe metadata — nothing translated the outline's actual text. Exposing it as a user-facing choice without fixing this would have been a hollow, misleading fix. `generate.py`'s new `_apply_translation()` calls `AIPort.translate()` on every slide's title, bullets, and notes when a non-English language is requested and AI is available; a translation failure on any single piece of text degrades to the original English (per the existing `AIPort.translate()` contract) rather than blocking the rest of generation.

**Also fixed, found during this work:** two more instances of the same `str_replace`-boundary bug from ADR-033 (a function's `def` header line silently dropped, merging its body into the previous function as unreachable-but-syntactically-valid trailing statements) — one in `test_ai_pipeline_port.py`, one in `backend/engines/generate.py` itself. Neither caused a test failure (Python doesn't error on dead code, it just runs it), which is exactly why this class of editing mistake is dangerous — caught only by manually re-reading the affected files line-by-line rather than trusting a green test run alone.

**Status:** Accepted. New tests: 4 boundary-level tests confirming the real `_post_json`/`get` functions attach the User-Agent to actual `urllib.request.Request` objects (not just testing the header-merge helper in isolation); 6 tests confirming `json_mode` is requested for `propose_structure` and correctly NOT requested for `rewrite` across Gemini/Groq/local models; 4 tests for `target_slide_count` hint threading (including through the composite cascade) and NullAdapter's graceful ignore; 3 tests for the new translation behavior (applies, skips for English, degrades safely on failure). Full suite: 223/223 passing.

## ADR-035 — Real HTTP-Level Integration Tests

**Context:** Every test in this codebase through ADR-034 exercised engines and adapters directly (`generate_presentation(...)`, `adapter.propose_structure(...)`, etc.) — never a real request through the actual FastAPI/Starlette HTTP stack. This was a named, repeated gap: two real bugs (the zip-bundling response shape in ADR-030, the speaker-notes-in-visible-body bug in ADR-029) shipped and were only caught by a human manually testing a real deployment, precisely because a direct engine call never touches routing, response headers, content-type negotiation, multipart parsing, or query-param binding the way an actual HTTP request does.

**Decision — FastAPI's TestClient, not a bespoke HTTP mock.** `tests/integration/test_api_http.py` uses `fastapi.testclient.TestClient` (Starlette under the hood) as a real client against `backend.api.main:app` — genuine HTTP request/response objects, real routing, real header handling, real multipart file uploads. Requires `httpx2` (Starlette's TestClient dependency in this environment's package version) — added to `requirements.txt` with a comment marking it as test-only, following this project's existing convention of a single requirements file rather than a separate dev-requirements split (matches how `pytest` is already there for the same reason).

**Decision — the context-manager form of TestClient, deliberately.** `with TestClient(app) as client:` rather than a bare `TestClient(app)` — this is what actually fires FastAPI's startup lifecycle, which starts the in-process worker thread (`backend/api/main.py`'s worker loop). Without it, every `/generate/async` test would enqueue a job that nothing ever processes and hang forever polling `/jobs/{id}`. This detail is easy to get wrong silently (a bare constructor doesn't error, it just never starts the worker), so it's called out explicitly in the test file's module docstring.

**Decision — every registry singleton reset per test, AI/media forced off by default.** A shared `reset_all_registry_singletons` autouse fixture zeroes every registry-cached adapter (queue, storage, auth, AI, media, research) before each test, giving fresh in-memory SQLite per test (no cross-test pollution — two tests both registering `alice@example.com` would otherwise collide) and forcing `OPENPRESENT_AI_ADAPTER=null` / `OPENPRESENT_RESEARCH_ADAPTER=null` so this suite never depends on live network calls or real API keys. This tests OpenPresent's own HTTP surface, not third-party provider availability — consistent with every other test in this codebase's approach to external dependencies.

**Coverage added, 18 tests:** root/health routing (regression for the earlier `/` 404 issue); sync document upload returning a real zip bundle vs. a bare pptx when `bundle_speaker_notes=false`; unsupported-file-type (400) and corrupt-file (422) error paths; the ADR-034 `audience_type`/`language`/`target_slide_count` params actually reaching the route; sync topic generation with `X-Structure-Source`/`X-Quality-Score` headers and slide-count clamping; full async round trips for both document and topic flows (enqueue → real worker-thread processing → poll → download, not a mocked worker); unknown-job-id 404s; and a full auth flow over real HTTP — register, login, generate as an authenticated user, confirm project isolation between two accounts, confirm 401 with no auth header, confirm 409 on duplicate registration, confirm 401 on wrong password.

**Bugs found while writing this suite, both in the new tests themselves, not the app:** an assertion using `.__length_hint__()` on a generator (should have been a plain `len(list(...))`), and an assumption that duplicate registration returns 400 when the API correctly returns 409 (Conflict is the more correct REST status for "resource already exists" — the test's expectation was wrong, not the API).

**Also fixed while in this file:** `@app.on_event("startup")` is deprecated in the FastAPI version this project pins (surfaced as a `DeprecationWarning` the moment real HTTP tests started exercising app startup, which no prior test ever did). Migrated to FastAPI's current `lifespan` context-manager pattern — same behavior (daemon worker thread started once, killed with the process), current API shape.

**What this does NOT address:** live provider API drift (the exact class of bug fixed in ADR-034 — stale model names, deprecated endpoints) has no automated detection here or anywhere else in this codebase; that would require real network calls against real provider APIs with real credentials, which doesn't belong in a hermetic test suite. That gap is explicitly still open. Also open: no CI pipeline actually runs this suite on every push — it exists and passes, but nothing yet enforces that it keeps passing automatically.

**Status:** Accepted. Full suite: 241/241 passing (223 prior + 18 new).

## ADR-036 — CI Pipeline and Automated Live Provider Drift Detection

**Context:** Two gaps named explicitly in ADR-035's "what this does NOT address": no CI pipeline enforced the 241-test suite automatically, and no automated mechanism detected live provider drift (stale model names, deprecated endpoints — the exact bug class fixed live across ADR-031/033/034) — every one of those was caught only after a human read production logs following a real user's failed generation.

**Decision — two separate GitHub Actions workflows, not one.** `ci.yml` (hermetic, every push, zero secrets) and `provider-drift-check.yml` (live, scheduled, requires secrets) are deliberately independent rather than one workflow with conditional steps. The reasoning: a code push and a third-party API outage are different failure signals that deserve different responses — a push that breaks the hermetic suite should block that PR immediately; a provider going down overnight should not block anyone's unrelated PR the next morning. Conflating them into one workflow would make every push's pass/fail status depend partly on third-party availability, which is exactly the "CI should never depend on live network" property being deliberately protected here.

**Decision — `ci.yml` requires zero secrets, on purpose.** The entire hermetic suite (`tests/contract/`, `tests/integration/`) was already built to mock or force-disable every AI/media/research provider (autouse fixtures throughout, most recently `test_api_http.py`'s `reset_all_registry_singletons` — ADR-035). `ci.yml` explicitly runs `pytest tests/ --ignore=tests/smoke` — the `--ignore` matters: `tests/smoke/` lives under `tests/`, and two of its checks (Wikipedia, Wikimedia) need no API key at all, so without the explicit exclusion they'd run on every single push too, silently making CI depend on live third-party availability despite every other design choice here working to prevent exactly that. Caught by testing the actual CI command locally before considering this done, not assumed correct from the workflow YAML alone.

**Decision — `tests/smoke/test_live_provider_drift.py` exercises the real adapter classes' real methods, not reimplemented HTTP calls.** The goal is catching drift in exactly the code path a real generation hits — a hand-rolled "ping the API" check could pass while the actual adapter's prompt-building or response-parsing logic (which is what actually broke in ADR-034's Bug 4, a JSON-mode threading issue, not a raw connectivity issue) stays silently broken. Every provider gets `generate_strategy()` tested (cheapest pipeline call, proves auth + model existence + JSON parsing); Gemini, Groq, and HuggingFace additionally get `_propose_structure_raising()` tested specifically, since that's the exact method/path that had its own separate, different bug (JSON mode) from the pipeline stages — a smoke test only covering `generate_strategy` would not have caught it. Every test skips (not fails, not errors) when its required API key isn't set, via a shared `_require_env()` helper — safe to run in any environment, including this one with zero keys configured.

**Decision — automatic issue filing, not just a red X in the Actions tab.** `provider-drift-check.yml` uses `actions/github-script` to open a GitHub issue labeled `provider-drift` on failure (or comment on an existing open one, to avoid duplicate-issue spam across consecutive daily failures), and automatically closes it with a comment once the check passes again. This is what makes "automated detection" mean something more than "a workflow exists" — a failure becomes a visible, trackable, self-resolving artifact in the repo's issue tracker, not something that only a person who happens to check the Actions tab would ever see.

**What this does NOT address:** no branch protection rule is configured to actually block a merge on `ci.yml` failure — that's a one-time GitHub repository Settings change (Settings → Branches), not something a workflow YAML file can configure on its own; documented explicitly in the README rather than left as a silent gap. The drift-check schedule (daily) is a judgment call, not a guarantee — a provider could still break and go undetected for up to ~24 hours between scheduled runs (the `workflow_dispatch` manual trigger exists for on-demand checks in the meantime).

**Verification note:** the two no-key-needed smoke tests (Wikipedia, Wikimedia) were confirmed to correctly skip-vs-fail-vs-run in every relevant scenario except one: this sandboxed development environment has no network route to `wikipedia.org`/`wikimedia.org` at all (not in its allowed-domains list), so those two tests fail here specifically due to the sandbox's own network restriction, not a code defect — noted explicitly rather than silently working around it by weakening the assertions, since doing so would have defeated the tests' actual purpose on a real GitHub Actions runner, which has full internet access.

**Status:** Accepted. 14 new smoke tests (12 skip without their provider's key configured, verified locally; 2 always-run tests verified logically correct but not executable end-to-end in this sandboxed environment specifically). Hermetic suite unaffected: 241/241 still passing via the exact command `ci.yml` runs.

## ADR-037 — Root Conftest Fixes a Real CI Failure: "Hermetic" Tests That Weren't

**Context:** The very first real run of `ci.yml` (ADR-036) failed: `test_export_unaffected_when_media_adapter_unavailable` passed in every local/sandboxed run but failed on GitHub Actions with a genuinely embedded photo where the test expected zero. Root cause: `registry.get_media_adapter()` and `get_research_adapter()` both include Wikimedia/Wikipedia in their default provider list unconditionally, no API key required — a deliberate design decision (ADR-029/030's "universal fallback, no key needed"). The failing test's docstring assumed "no keys configured" meant "`NullMediaAdapter`, zero network calls" — an assumption that was true before ADR-029 and silently went stale the moment Wikimedia became an always-on default, with nothing left to catch it.

**Why this passed everywhere it was developed and only failed in CI:** this sandboxed development environment has no network route to `wikipedia.org`/`wikimedia.org` at all (confirmed: neither domain is in its allowed-domains list). The real Wikimedia call inside the test's code path failed silently (caught by the adapter's own try/except, per its designed graceful degradation) and returned no candidates — which *looked* like "no provider configured," the right test outcome, for the wrong reason. GitHub Actions runners have full internet access; the same call there genuinely succeeds and embeds a real photo. This is the second time in this project a sandbox-vs-real-network difference has masked a real gap (the same shape of issue as ADR-036's own note about the two smoke tests) — worth naming as a recurring category, not a one-off.

**Scope of the actual exposure:** grepping for test files that call `generate_presentation`/`generate_presentation_from_topic` without explicitly mocking `get_media_adapter`/`get_research_adapter` turned up `test_layout_classifier.py` and `test_end_to_end.py` in addition to the one that actually failed — both silently making live network calls in any real-network CI environment, just without an assertion strict enough to notice. This was never a single test's bug; it was every test in the suite that didn't happen to explicitly mock these two functions, protected only by an accident of where development happened.

**Decision — a single root `tests/conftest.py`, not per-file patches.** An autouse, function-scoped fixture (`_hermetic_registry_defaults`) monkeypatches `get_ai_adapter`, `get_media_adapter`, and `get_research_adapter` to their Null variants for every test under `tests/`, closing the gap for every current and future test file at once rather than requiring each one to remember to opt in. Individual tests remain free to override any of the three with their own `monkeypatch.setattr` call within the test body — pytest's monkeypatch stacking means a test's own patch simply wins for that test, which is exactly how every existing `FakeMediaAdapter`/`FakeAIAdapter`-style test already worked and continues to.

**Decision — explicitly excluded from `tests/smoke/`.** Live provider drift tests construct adapters directly (`GeminiAdapter(api_key=os.environ[...])`), bypassing the registry entirely, so this fixture has no functional effect on them either way — the explicit path-based skip in the fixture exists for clarity of intent (a reader shouldn't have to reason about registry mocking when reading smoke tests), not because omitting it would have broken anything.

**Decision — two tests that test the REAL registry wiring explicitly opt out.** `test_registry_builds_composite_with_wikipedia_by_default` and `test_registry_research_can_be_fully_disabled` (`test_research_port.py`) exist specifically to verify `get_research_adapter()`'s own real logic — mocking the function away would make them test nothing. Each calls `monkeypatch.undo()` as its first line, reverting the autouse fixture's patch (and anything else monkeypatch has touched so far in that test) before proceeding with its own real-function assertions. This was the only genuine collision found across the full suite.

**Verification, not just a fix:** `test_conftest_hermeticity.py` adds 5 tests proving the fixture itself works — that all three registry functions default to Null within any normal test, that a test's own override still takes precedence, and an end-to-end version of the originally-failing scenario going through the real engine rather than just checking the registry function in isolation. The original bug is now caught by a test that fails for the RIGHT reason if this fixture is ever accidentally removed, not just fixed once and left unguarded.

**Status:** Accepted. Full hermetic suite: 246/246 passing (241 prior + 5 new hermeticity regression tests), confirmed via the exact command `ci.yml` runs (`pytest tests/ --ignore=tests/smoke`). `tests/smoke/` confirmed unaffected — same 12 skip / 2 sandbox-network-blocked pattern as ADR-036, unchanged.

## ADR-038 — Slide-Level Editing and AI-Assisted Partial Regeneration

**Context:** Every generation capability through ADR-037 operates on the whole deck — regenerating one unsatisfying slide meant re-running the entire pipeline (5+ AI calls, real cost and latency) and risked silently changing slides the user was already happy with. Product request: let a user fix one slide without touching the rest.

**Bug found and fixed before building anything on top of it:** both storage adapters' `_recipe_from_dict` (`sqlite_storage.py`, `postgres_storage.py`) silently dropped `layout_type` and `image_query` on every load — reverting to the `Slide` dataclass's defaults (`"bullet_list"`, `None`) the instant a saved project was fetched back from storage. This is a real, pre-existing bug (not introduced here) that had gone unnoticed because nothing previously round-tripped a project through storage and then checked those two fields — the existing `test_save_and_get_recipe_roundtrip` test's fixture happened to only use default values, so the bug was invisible to it. Found specifically because slide editing's core operation is "load a Recipe from storage, touch one slide, save it back" — a workflow that would have silently discarded every AI-planned layout and every embedded image on every edit, for every slide in the deck, not just the one being edited. Fixed in both adapters; a new regression test (`test_save_and_get_roundtrip_preserves_layout_type_and_image_query`) uses genuinely non-default values specifically so this can't silently reoccur.

**Decision — two distinct operations, not one "edit" endpoint.** `edit_slide_manually` (no AI, direct field update, always available) and `regenerate_slide_ai` (AI-assisted rewrite with optional freeform instructions, requires a configured provider) are separate engine functions and separate HTTP verbs on the same URL (`PATCH` vs `POST .../regenerate`) — not one endpoint with a `use_ai: bool` flag. The two have different failure modes (manual edit never fails for lack of AI; AI regeneration has no honest deterministic fallback and must surface unavailability clearly) and different mental models for the person using them, which a single conflated endpoint would blur.

**Decision — no deterministic fallback for `regenerate_slide_ai`, unlike everywhere else in this codebase.** Every other AI capability degrades to something reasonable when AI is unavailable (the topic-template outline, the rule-based document structure, the unmodified original text for `AIPort` methods). Single-slide regeneration has no honest equivalent — there is no rule-based way to produce "a genuinely different, better version of this slide" the way there's a rule-based way to produce "a structurally valid deck." `AIUnavailableError` surfaces as a real `503` over HTTP rather than silently returning the slide unchanged (which would look like a successful regeneration that did nothing) or synthesizing filler content (which would be worse than the original). The manual-edit endpoint is the documented alternative, always available regardless.

**Decision — no persisted `PresentationStrategy` needed for regeneration.** `SlideRegenerationContext` is assembled fresh from the stored `Recipe` each time: `source_text` (already "Topic: X" or a document excerpt), `audience_type`, `language`, and every other slide's title (for narrative consistency and to avoid the regenerated slide duplicating another slide's content). The original generation's `narrative_style`/`title_angle`/`key_themes` — useful during full-deck generation — were judged not worth persisting just for this: the surrounding slides' actual titles are a more concrete, always-current consistency signal than a strategy object that could drift out of sync with slides that were manually edited since generation.

**Decision — `regenerate_slide` shares the existing `_JSONPipelineMixin`/`CompositeAIAdapter` machinery.** Implemented as one more method on the mixin (prompt builder + strict JSON parser, same discipline as every other stage) and one more cascaded method on the composite — every existing AI provider (Gemini, Groq, OpenRouter, HuggingFace, local models) gets this capability automatically via the same `_call_model` primitive each already implements, no per-provider code needed. Uses the floor token budget/timeout (`_TOKEN_BUDGET_FLOOR`/`_READ_TIMEOUT_FLOOR`) since a single slide is always a small request regardless of overall deck size.

**Decision — regeneration and manual edits never touch `layout_type`/`image_query`.** Documented as a real scope boundary, not silently glossed over: if a regenerated slide's content shifts enough that its original layout no longer fits (was `"process"`, new content is stats-heavy), that mismatch isn't auto-corrected. Re-planning layout on every edit would mean an extra AI call and a potential new image fetch (cost, latency, image-provider quota) on an action a user will likely invoke several times while iterating — judged not worth it for this increment. A natural follow-up, not built here.

**New endpoints:** `GET /projects/{id}/slides/{order}` (full slide detail — bullets/notes/layout, not just the title `GET /projects/{id}` already gives), `PATCH /projects/{id}/slides/{order}` (manual edit), `POST /projects/{id}/slides/{order}/regenerate` (AI regenerate). All three require ownership (401 unauthenticated, 404 for another user's project — same isolation guarantee as every existing project endpoint, verified over real HTTP in `test_api_http.py`, not just at the engine level).

**Frontend:** the existing (previously read-only) `frontend/app/projects/[id]/page.tsx` gained inline expand-to-edit per slide — a title/bullets/notes form (manual save) plus an optional-instructions field with a "Regenerate with AI" button, sharing the same expanded view. A 503 from the regenerate endpoint surfaces as a specific, actionable message ("No AI provider is configured — try editing this slide manually instead") rather than a generic error.

**Status:** Accepted. 16 new engine-level tests (`test_edit_slide_engine.py`) covering manual edits (partial field updates, persistence, ownership, unknown project/slide), AI regeneration (unavailable-raises, correct context assembly, other-slides-untouched, layout/image-query preservation, failure logging), plus 6 new AI-pipeline tests for `regenerate_slide` itself (prompt content, cascading, malformed-response handling) and 1 storage regression test for the layout_type/image_query bug. 10 new real-HTTP integration tests (`test_api_http.py`) covering all three new endpoints end to end, including the 503-not-500 guarantee and cross-account isolation. Full suite: 279/279 passing. Frontend typechecks and builds clean.

## ADR-039 — Slide Editing Was Unreachable From The Actual Product: Sync Generation Never Saved a Project

**Context:** Product report after ADR-038 shipped: "there was no way to edit on the user interface." The feature itself worked correctly — every engine and HTTP test for it passed — but it was completely unreachable from how the product is actually used.

**Root cause:** the homepage (the only entry point most people ever use) calls `POST /generate` and `POST /generate/topic` — the **sync** endpoints — for both the document-upload and topic-generation forms. Neither sync endpoint ever accepted an `Authorization` header or persisted a project, regardless of whether the caller was logged in; only the **async** endpoints (`/generate/async`, `/generate/topic/async`) did that, because the "save if `owner_id` present" logic lived in the worker, which only the async path goes through. The frontend's own sync-call functions (`generateSync`, `generateFromTopicSync` in `api-client.ts`) compounded this by never sending an auth token in the first place, even though the user might be logged in. Net effect: a logged-in user generating from the actual website got a downloaded file and *nothing else* — no project was ever created, so there was categorically nothing for the slide editor (ADR-038) to open. The feature was real; the door to it didn't exist.

**A second, related bug found while fixing the first:** even after adding project-saving to the sync endpoints and returning the new project's id in an `X-Project-Id` response header, that header would have been silently invisible to the frontend's JavaScript anyway. Cross-origin responses (Vercel frontend, Render backend — different origins) only expose a small default set of "safe" headers (`Content-Type`, `Content-Length`, etc.) to browser JS; anything else needs an explicit `Access-Control-Expose-Headers` entry in the CORS configuration. This project's `CORSMiddleware` had never set one — meaning `X-Structure-Source` and `X-Quality-Score` (both already returned by `/generate/topic`, added back in ADR-030) had *also* been silently unreadable by frontend code this whole time, just never surfaced as a bug because nothing in the UI had tried to read them yet.

**Fix:**
1. `/generate` and `/generate/topic` (sync) now accept `authorization`, resolve the user the same way the async endpoints already do, and save a project when one is present — same "save if `owner_id`" behavior, just added to the path real users actually take.
2. Both endpoints return `X-Project-Id` in the response headers when a project was saved (absent for anonymous requests — verified explicitly by a test, not just assumed).
3. `CORSMiddleware` gained `expose_headers=["X-Project-Id", "X-Structure-Source", "X-Quality-Score"]` — fixing both the new header and the two pre-existing ones that had been quietly broken since ADR-030.
4. `generateSync`/`generateFromTopicSync` (frontend) now send `authHeaders()` and return `{ blob, projectId }` instead of a bare `Blob`.
5. Both homepage forms (`TopicForm`, `DocumentForm`) show an "Edit this presentation, slide by slide →" link to `/projects/{id}` when a project was saved, or a "create a free account" nudge when it wasn't (anonymous generation still works exactly as before — this is additive, not a new requirement to use the product at all).

**Why this wasn't caught by ADR-038's own tests:** every test for slide editing (engine-level and HTTP-level) started from a project created via `/generate/async`, because that was the only path that had ever created one. The tests were correct about the feature they tested; they never exercised the actual path a real user takes to reach it, so a whole category of "is this feature reachable at all" bugs had no test surface to be caught by.

**Status:** Accepted. 4 new HTTP-level tests: sync document generation saves a project when authenticated (and the project is genuinely re-fetchable afterward, not just a header check), sync generation saves nothing when anonymous, sync topic generation saves a project when authenticated, and a direct assertion that all three custom headers are actually present in `CORSMiddleware`'s `expose_headers` config (not inferred from behavior — read directly off the middleware's registered kwargs). Full suite: 283/283 passing. Frontend typechecks and builds clean.

## ADR-040 — v3 Studio Frontend, and Real Per-Stage Job Progress

**Context:** Kicking off OpenPresent v3 (the pivot from a presentation
generator to a broader AI creation platform, per the vision doc). First
concrete deliverable: a new Claude Code–style frontend (`/studio` —
sidebar, chat thread, live preview panel) as the v3 entry point,
without touching or breaking any existing v2 page. The new chat UI's
mid-generation step indicators initially had no real backend data to
draw from — `GET /jobs/{id}` only ever returned
`pending/running/done/failed`, nothing about which of the 5 real
pipeline stages (Strategy → Outline → Content → Layout → Quality
Review, `ai_generate.py`'s own module docstring) was actually running.

**Decision (frontend):** `/studio` is a fully separate layout
(`components/AppShell.tsx` swaps in `Sidebar.tsx` instead of the v2
`NavBar` based on route, client-side), so every v2 page — `/`,
`/dashboard`, `/login`, `/register`, `/projects/[id]` — is byte-for-byte
unchanged. New `--op-*` CSS tokens (violet→blue gradient, matching the
new logo) are additive alongside the existing v2 "desk lamp" tokens in
`globals.css`, not a replacement. `/studio` calls the real
`generateFromTopicAsync` / `generateAsync` / `getJobStatus` /
`getProject` — there is no mock or simulated backend behind it.

**Decision (backend):** rather than leave the step indicators as a
pure cosmetic timer indefinitely, `QueuePort` gained a `stage: str |
None` field on `Job` and an `update_stage(job_id, stage)` method
(implemented in both `SqliteQueueAdapter` and `PostgresQueueAdapter` —
the latter via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, safe on the
existing prod table with no manual migration step). `generate_
presentation_from_topic()` takes an optional `on_stage` callback and
reports 6 coarse labels as it runs (`understanding_request →
building_outline → generating_content → designing_slides →
selecting_visuals → applying_design` — deliberately fewer than the
full internal stage list, chosen for what's meaningful to show a user,
not every internal function call). The worker wires this to
`queue.update_stage`. `GET /jobs/{id}` now includes `stage` in its
response, but only while `status == "running"` — redundant once done,
and deliberately never fabricated for a state that isn't actually
running.

**Scope limits, stated plainly:**
1. ~~Only `generate_presentation_from_topic` (topic mode) reports real
   stages.~~ **Closed same-session:** `generate_presentation`
   (document-upload mode, `engines/generate.py`) now also takes an
   `on_stage` callback and reports 4 of the 6 shared labels
   (`understanding_request → building_outline → generating_content →
   applying_design` — it skips `designing_slides`/`selecting_visuals`
   because that pipeline genuinely has no separate layout-planning or
   image-selection call to report on; padding in stages that don't
   correspond to real work would make the indicator lie in the other
   direction). `generating_content` itself only fires when an AI
   adapter is actually available, since with `NullAdapter` there is no
   content-generation step to report. `GET /jobs/{id}`'s `stage` field
   is job-type-agnostic — no endpoint change was needed, it already
   read `job.stage` generically.
2. `on_stage` is explicitly best-effort: every call site wraps it in a
   try/except that reports to Sentry/Bugsink and swallows the error —
   a broken progress sink must never break or slow an otherwise-
   successful generation. Covered by a dedicated test for each engine.
3. No new database tables, no brand memory, no document/infographic/
   diagram generation yet — see `V3_ROADMAP.md` (delivered alongside
   this ADR) for the full phased plan. This entry is Phase 1 + Phase 2
   from that roadmap, not the whole thing.

**Status:** Accepted. 12 new tests total: 4 on `SqliteQueueAdapter.
update_stage` (sets/reads correctly, silent no-op on an unknown job
id, survives into a completed job's record), 3 on the topic engine's
`on_stage` orchestration (full 6-stage order on the AI path, correct
shorter sequence on deterministic fallback, callback-raises-survives),
3 on the document engine's `on_stage` orchestration (4-stage order
with AI available, 3-stage order without, callback-raises-survives),
2 HTTP-level (`stage` present and correct while running, absent once
done). Full suite: 295/295 passing. Frontend typechecks and builds
clean (`/studio` route confirmed in build output).

*Next entry: ADR-041.*

## ADR-041 — Documents as a Second Output Type (v3 Phase 3)

**Context:** v3 roadmap Phase 3: reuse the existing 5-stage pipeline
and Recipe/Outline model for a genuinely different deliverable — a
real Word document (proposal, report, exec summary) instead of a
slide deck — rather than building a parallel document-generation
system. The roadmap's own framing was "only Layout/Export differ,"
and that held up exactly as expected: no changes to Strategy, Outline
Structure, Slide Content, Layout Planning, or Quality Review were
needed anywhere.

**Decision:** new `DocumentDocxExportAdapter`
(`backend/adapters/export/document_docx_adapter.py`, format_id
`document_docx`), registered in `registry._EXPORT_ADAPTERS` alongside
`pptx`. It consumes the exact same `Recipe` every other export format
does. No new endpoint, no new job type, no new request field beyond
the `export_format` string every generation endpoint already accepted
— `export_format="document_docx"` on `/generate/topic`,
`/generate/topic/async`, `/generate`, `/generate/async`, or
`/projects/{id}/export` just works.

This is deliberately a different thing from the existing
`SpeakerNotesDocxExportAdapter` (`docx_notes_adapter.py`, ADR-030):
that one is a presenter's companion aid, framed around slides
("Slide 3: ...", "On-slide content:"). This adapter is meant to BE
the deliverable — a document a reader opens and reads top to bottom
with no reference to slides anywhere in it. Each `Slide` becomes a
document section (title → heading, bullets → either a real Word
bullet list or, when a section is a single sentence-length bullet,
folded into a plain paragraph instead — deliberately conservative
about forcing every bullet into prose, since that's a common way
AI-authored documents read worse than a well-formatted list, not
better). Speaker notes are intentionally never rendered — they exist
for someone reading a deck aloud, which has no meaning once the
document itself is the deliverable.

**A real latent bug found and fixed while wiring this in:** every
filename-generating call site in `api/main.py`
(`/generate/topic`, `/generate/topic/async`'s job-download route,
`/generate`, and `/projects/{id}/export`) built the download filename
as `f'presentation.{export_format}'` — harmless while `pptx` was the
only registered format (`presentation.pptx`), silently wrong the
moment a second format existed (`presentation.document_docx` is not a
filename anyone recognizes). Added `_download_filename()` and
`_MEDIA_TYPES["document_docx"]`, fixed all 4 call sites. The existing
`bundle_speaker_notes` guard was already correctly keyed to
`export_format == "pptx"` specifically (not "truthy bundle flag"), so
document exports were never at risk of being incorrectly zipped with
a speaker-notes companion that makes no sense for them — confirmed by
test, not just read.

**Status:** Accepted. 8 new adapter-level tests
(`tests/contract/test_document_docx_adapter.py`) covering format_id,
valid-docx output, title-page-not-slide-1-heading framing, section
headings present, single-sentence-bullet-becomes-paragraph, multi-
bullet-stays-a-list, notes never rendered, and an empty outline still
producing a valid (if minimal) document. 3 new HTTP-level tests
covering sync generation, the bundling guard correctly skipping this
format, and a full async round trip through job polling and download.

*Next entry: ADR-042.*

## ADR-042 — Worker Thread Graceful Shutdown (found while testing ADR-041)

**Context:** discovered, not designed for — the new document-export
HTTP tests exposed an existing test (`test_jobs_endpoint_surfaces_
stage_while_running`, from ADR-040) intermittently failing with a 404
on a job that had genuinely just been enqueued. Root cause traced to
`_in_process_worker_loop` (`api/main.py`): the code's own prior
comment said it plainly — *"Nothing runs on shutdown; the daemon
thread is killed with the process."* True and harmless in production
(one process, one worker thread, for its whole lifetime), but every
test using `with TestClient(app) as client:` triggers a fresh
lifespan startup, spawning a new daemon worker thread each time —
and since none of them ever stopped, a test suite with many HTTP
tests accumulated an increasing number of zombie threads over a
single pytest run, all still looping `process_one_job()` and all
calling `registry.get_queue_adapter()` every iteration.

That getter's lazy-singleton pattern (`if _instance is None: _instance
= ...`) is a classic non-atomic check-then-set race under real
threading. With enough zombie threads calling it concurrently right
as each test's autouse fixture reset the singleton to `None`, a
zombie thread from an *earlier* test could occasionally win the
re-initialization race for the *current* test's registry state —
leaving the test's own `queue` variable and the API route handler's
`registry.get_queue_adapter()` call pointing at two different
in-memory SQLite databases, hence the 404 (right endpoint, wrong
database, job genuinely didn't exist there).

**Decision:** two fixes, addressing both the leak and the underlying
race it was surfacing:
1. `_in_process_worker_loop` now takes a `threading.Event` and checks
   it every iteration (via `Event.wait()` instead of `time.sleep()`,
   so a stop request interrupts the wait immediately). `_lifespan`
   creates the event, starts the thread as before, and on shutdown
   (after `yield`) sets the event and joins the thread with a 5s
   timeout — bounded so a single unusually-slow in-flight job can
   never hang app shutdown forever.
2. `registry.get_queue_adapter()` — the one getter actually implicated
   by a real, reproduced failure — now guards its lazy init with a
   `threading.Lock` and a double-checked-locking pattern, closing the
   race directly rather than relying solely on "there should only
   ever be one thread calling this" now being true again.

**Scope, stated plainly:** fix #2 is deliberately narrow — only
`get_queue_adapter()`, not all seven `get_*_adapter()` singleton
getters in `registry.py`, all of which share the same non-atomic
pattern and are structurally exposed to the identical race if a
future caller ever creates adapters from more than one thread. Not
fixed speculatively here since only the queue getter has an actual
reproduced failure behind it; worth a dedicated pass if/when a second
one does.

**Status:** Accepted. No new dedicated unit test for the threading fix
itself (reliably unit-testing a race condition's *absence* without a
flaky or artificially slow test is its own can of worms, not worth
opening for this) — verified instead by running the full suite 5
consecutive times end-to-end, 306/306 passing every time, where
before this fix `test_jobs_endpoint_surfaces_stage_while_running`
failed roughly 1 run in 3. Frontend typechecks and builds clean, `/studio` unaffected by either
change in this entry.

*Next entry: ADR-043.*

## ADR-043 — Cost Circuit Breaker

**Context:** the #1 item in the original project handoff doc's
"actually risky right now" list, present before v3 work began: *"A
single generation can now trigger 6+ AI calls (strategy/outline/
content/layout/review/research), and editing/regeneration adds more
on top. Nothing caps spend."* Adding a second output type (ADR-041)
made this strictly worse — every format multiplies the same uncapped
surface, not just presentations. The v3 roadmap itself flagged this
as something that should happen "before Phase 3 ships"; it's landing
right after instead, which is late relative to that intent but still
before Phase 4+ adds further surface.

**Decision:** new `QuotaPort` (`backend/ports/quota.py`) — deliberately
just a fixed-window counter, not a general rate limiter (no burst
logic, no leaky bucket, no IP-based abuse heuristics). The port's only
job is "how many attempts landed here in this window" — policy (what
limit, what to do when exceeded) lives entirely in the caller
(`api/main.py`), not the port, matching this codebase's existing
separation between ports (mechanism) and engines/API (policy).
`SqliteQuotaAdapter`/`PostgresQuotaAdapter` mirror the existing queue
adapters' structure exactly, including applying the ADR-042 lesson
from the start this time: `get_quota_adapter()` uses the same
double-checked-locking pattern as the now-fixed `get_queue_adapter()`,
rather than waiting to discover the same race independently.

All 4 generation endpoints (`/generate`, `/generate/topic`,
`/generate/async`, `/generate/topic/async`) call
`_enforce_generation_quota(user, request)` as the very first thing
after resolving the caller's identity — before file reads, before any
AI/export work, before the async path even enqueues a job. A rejected
request costs one counter increment and nothing else. Signed-in users
are keyed by `user.id` (default cap 30/day); anonymous callers are
keyed by IP (default cap 5/day, deliberately lower since anonymous
abuse can't be followed up on the way an account can). Both caps are
env-var configurable (`OPENPRESENT_DAILY_GENERATION_LIMIT_USER`/
`_ANON`) and read at call time, not baked into a module-level constant
at import — a real bug caught by the tests themselves (see below).
Window is a fixed 24h bucket keyed to the UTC calendar day, not a
rolling window — simpler to reason about and to explain to a user
("resets at midnight UTC") than a sliding one, and precision here
doesn't need to be tighter than that for a cost cap.

**A real bug the tests caught, not designed around from the start:**
the first version read the two limit env vars into module-level
constants (`GENERATION_LIMIT_USER = int(os.environ.get(...))`) at
`api/main.py` import time. `monkeypatch.setenv` in a test — or any
config change in production without a full process restart — would
silently have no effect, since the constant was already baked in
before the env var changed. All 3 of the first HTTP-level quota tests
failed on first run with exactly this symptom (asserted 429, got 200).
Fixed by reading the env vars inside small helper functions
(`_generation_limit_user()`/`_generation_limit_anon()`) called at
request time instead of at import time.

**Scope, stated plainly:** this caps *request volume* per identity,
which is a reasonable proxy for spend but not spend itself — a
provider price change, a slow month of many large `slide_count`
requests, or a future format with a very different cost profile
(e.g. Phase 6's infographics/posters, if those end up image-generation
heavy) could all still add up differently than this counter assumes.
Good enough as the circuit breaker the handoff doc asked for; a
genuine cost-based cap (estimating $ per request type, not just
counting requests) is a real future upgrade, not represented here.

**Status:** Accepted. 5 new adapter-level tests
(`tests/contract/test_quota_port.py`: first attempt returns 1,
repeated attempts increment, different keys independent, count keeps
incrementing past a hypothetical limit rather than the port enforcing
one itself, and a new window genuinely resets the count — verified
with a real 1-second window and a real sleep, not mocked time). 4 new
HTTP-level tests: anonymous callers blocked after their limit,
the gate fires before any generation work even with a limit of zero,
the async enqueue path is gated identically to the sync path (not
just one of the two), and two different user accounts have genuinely
independent quota buckets. Full suite: 315/315 passing, run 3
consecutive times with no flakes. Frontend requires no changes —
`api-client.ts` already surfaced every endpoint's `detail` field on a
non-2xx response, so a 429's human-readable message reaches the
studio's existing error bubble with no new code path.

*Next entry: ADR-044.*

## ADR-044 — Project Workspace (v3 Phase 4)

**Context:** the vision doc's "central experience" — grouping
generated projects into named folders, per user request ("continue
building" after landing the cost circuit breaker). The bigger
architectural step of the four v3 phases delivered so far: every
previous phase (documents, real job progress, the quota gate) reused
existing tables end to end. This one genuinely adds a new one.

**Decision:** new `WorkspacePort` (`backend/ports/workspace.py`) —
named folders (id/name/owner/timestamps only) a user groups projects
into, kept deliberately separate from `StoragePort`'s existing
project data rather than merged into one bigger port. `StoragePort`
gained an optional `workspace_id` on `save_recipe`/`list_projects`
plus a new `unassign_workspace()` method; both are additive and
`workspace_id=None` reproduces exactly pre-ADR-044 behavior (existing
callers, existing tests, unaffected). `SqliteWorkspaceAdapter`/
`PostgresWorkspaceAdapter` mirror the existing adapter pattern
exactly (Postgres gets the projects table's new `workspace_id` column
via a safe `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, same as every
additive-column change since ADR-040), and `get_workspace_adapter()`
in `registry.py` applies the ADR-042/043 double-checked-locking
pattern from the start rather than being a fifth place that race gets
independently rediscovered.

**The one genuinely subtle design choice, stated plainly in the
port's own docstring so it's never accidentally reversed later:
deleting a workspace never deletes its projects.** A project's actual
generated content is the entire point of this product; an
organizational folder being deleted must never destroy it as a side
effect. `DELETE /workspaces/{id}` calls `StoragePort.
unassign_workspace()` (clearing `workspace_id` back to `None` on every
project inside it) *before* calling `WorkspacePort.delete_workspace()`
— deliberately in that order, so a crash between the two steps leaves
"workspace still exists, its projects already ungrouped" (recoverable
— just delete the now-empty workspace again) rather than "workspace
gone, projects silently pointing at a workspace_id that no longer
resolves for anyone" (a state nothing would ever surface to the user).

**API surface:** `POST/GET/PATCH/DELETE /workspaces`, `GET
/workspaces/{id}` (workspace plus its projects, one response), and
`GET /projects?workspace_id=...` for filtering (omitting the param
keeps returning everything, matching the pre-ADR-044 endpoint
exactly). All 4 generation endpoints (`/generate`, `/generate/topic`,
`/generate/async`, `/generate/topic/async`) accept an optional
`workspace_id` to assign a new project at creation time — validated
by a new `_resolve_workspace_id()` helper *before* any AI/export work
starts (same "gate first" discipline as ADR-043's quota check, which
this literally sits right next to in every endpoint). An unowned
`workspace_id` is rejected with `404`, not silently ignored or
silently reassigned to someone else's folder — not a data leak either
way (every listing stays owner_id-scoped regardless), just avoiding a
confusing state where a project points at a workspace_id its actual
owner can never see resolve in their own `list_workspaces()`.

An edit call site re-saving an existing project (e.g. a slide
regeneration) that doesn't pass `workspace_id` at all leaves the
project's existing workspace assignment untouched rather than wiping
it to `None` — explicit `None` was never a meaningful "unassign" input
worth designing for here (nothing in the product surface offers
"remove this project from its workspace" as a distinct action yet);
the real failure mode this guards against is a call site that simply
doesn't know about workspaces yet silently un-assigning things it was
never trying to touch.

**Status:** Accepted. 29 new tests: 10 on `WorkspacePort`/
`SqliteWorkspaceAdapter` (create/get roundtrip, not-found and
wrong-owner both return identical `None`/`False` rather than leaking
which case applies, list scoped and ordered correctly, rename and
delete both respect ownership), 8 on `StoragePort`'s new
`workspace_id` behavior (assignment reflected in listing, omitted
defaults to `None`, filtering works, re-saving without `workspace_id`
preserves the existing assignment, re-saving *with* a new one does
reassign, `unassign_workspace` clears the right rows and respects
ownership and is a no-op on an empty match), 11 HTTP-level end to end
(auth required, create/list/rename, per-user isolation, generation
assignable to a workspace at creation, an unowned `workspace_id`
rejected with 404 before any generation work, `/projects` filtering,
and — the one that actually exercises this entry's core design
guarantee — deleting a workspace through the real API and confirming
the project inside it is still fully fetchable afterward, just
ungrouped). Full suite: 344/344 passing, verified 3 consecutive clean
runs.

**Frontend, done same-session:** `api-client.ts` gained `workspaceId`
on both `TopicGenerateOptions` and `DocumentGenerateOptions`, plus
`listWorkspaces`/`createWorkspace`/`getWorkspace`/`renameWorkspace`/
`deleteWorkspace`. The sidebar's "Recent" section (flat list since
Phase 1) now sits alongside a real "Workspaces" section — expandable
folders (click to fetch and show that workspace's projects inline,
no separate route needed), a "+ New workspace" affordance, and a
per-row delete button that only appears on hover. Workspace creation
uses a plain `window.prompt()` rather than a styled modal — a
deliberate, stated MVP shortcut (see the code comment at the call
site), not a hidden gap. The studio composer gained a `<select>`
workspace picker next to the existing Slides/Document toggle,
defaulting to "No workspace" (ungrouped, unchanged pre-ADR-044
behavior) and populated from the real `listWorkspaces()` call.
Frontend typechecks and builds clean, `/studio` and the sidebar both
confirmed in the production build output.

*Next entry: ADR-045.*

## ADR-045 — Brand Memory (v3 Phase 5)

**Context:** the vision doc's Brand Memory section — "every project
should have a brand profile... all generated assets should follow
this automatically." Followed directly from Phase 4 (ADR-044): once
workspaces exist as a real concept, a brand profile keyed to a
workspace is one more table and one more input threaded into
generation, not a new pipeline.

**Decision:** new `BrandProfilePort` (`backend/ports/brand.py`) — a
strict 1:1 relationship with a workspace, enforced structurally by
keying the table directly on `workspace_id` as its primary key rather
than giving profiles their own id and a separate foreign-key column.
This matches the vision doc's own framing ("every workspace has a
brand profile," not "workspaces choose from a library of profiles")
and makes the 1:1 constraint impossible to violate by construction
rather than a convention callers have to remember.
`SqliteBrandAdapter`/`PostgresBrandAdapter` mirror every other
adapter's pattern, `get_brand_adapter()` in `registry.py` applies the
double-checked-locking fix from the start (ADR-042/043/044
precedent).

`set_brand_profile()` is a whole-record replace, not a partial merge
— stated plainly in the port's docstring and re-stated at the API
model (`BrandProfileRequest`) specifically because it's the one design
choice most likely to bite someone who assumes PATCH-like partial-
update semantics without reading the docstring first. `PUT
/workspaces/{id}/brand` always expects the full form. `BrandProfile.
is_empty()` (true when every field is blank) is what lets an
all-cleared profile behave identically to no profile ever having been
set — both produce zero prompt injection, checked by dedicated tests
that assert an empty and a `None` brand produce the same absence of a
brand block, not by relying on any date/random tiebreak.

**Where it actually plugs into generation:** `GenerationRequest`
(the topic pipeline's request object, `ports/ai_pipeline.py`) gained
an optional `brand: BrandProfile | None = None` field.
`json_pipeline_base.py`'s `_build_strategy_prompt` — the one shared
prompt-builder every real AI provider adapter inherits — appends a
brand block when `request.brand` is set and non-empty, framed
explicitly to the model as informing tone/narrative feel rather than
being a hard constraint: *"let it inform tone_notes and the overall
narrative feel, without overriding what actually fits this specific
topic."* Only the fields actually set are included (a brand profile
with only `tone` filled in doesn't inject placeholder text for the
unset color/audience/style fields). The API layer's new
`_fetch_brand_profile()` helper fetches the workspace's profile
(if any) right after `_resolve_workspace_id()` already validated
ownership — deliberately reusing that check rather than re-deriving
authorization logic a second time in a second place, same pattern
`_enforce_generation_quota` and `_resolve_workspace_id` already
established next to each other in every generation endpoint.

For the async path, a job payload has to be JSON-serializable (it's
persisted as JSON — see every queue adapter), so the enqueue side
sends the `BrandProfile`'s five content fields as a plain dict (or
`None`), and `generation_worker.py`'s new `_brand_from_payload()`
reconstructs the actual dataclass before calling the engine —
`workspace_id`/`owner_id`/timestamps are left at their dataclass
defaults on the reconstructed copy since they're not meaningful for
this transient, in-flight value (only the five content fields the
prompt-builder reads matter).

**Scope, stated plainly — one real limit remains:**
1. **Color mapping isn't wired into the deterministic theme/layout
   renderer.** A brand's `colors` field is free text the model reads
   as context ("Blue and purple, modern"), not something mapped onto
   the renderer's actual fixed theme palette. Mapping freeform color
   descriptions onto real design tokens is a genuinely separate,
   harder problem — worth its own pass once there's real usage data
   on what people type into this field, not guessed at speculatively
   here.

~~2. Only the topic-generation pipeline reads brand.~~ **Closed
same-session:** `generate_presentation` (document-upload mode,
`engines/generate.py`) now also accepts a `brand` parameter, threaded
into `_apply_title_enhancement` — the ONE AI touchpoint in that
pipeline actually about phrasing rather than content
(`propose_structure` is about document structure, not style, so it's
not a natural fit for brand tone the same way this is; same reasoning
the topic pipeline's Strategy stage used to decide where brand context
belongs). Specifically only `tone` and `visual_style` are read (the
two fields that are actually about phrasing) — `name`/`colors`/
`audience` being set has zero effect on the rewrite instructions,
confirmed by a dedicated test. Same job-payload serialize/reconstruct
pattern as the topic pipeline's async path, reusing the same
`_brand_from_payload()` helper rather than duplicating it.

**Status:** Accepted. 24 new tests at initial ship (see below), plus
7 more closing the document-mode gap same-session: 5 on
`_apply_title_enhancement`'s brand handling (tone+visual_style appear
in the rewrite instructions when set, unchanged when brand is `None`,
unchanged when brand is present-but-empty, unchanged when only
name/colors/audience are set, and an end-to-end call through the real
`generate_presentation()` with a brand profile still produces valid
output), 2 HTTP-level (document upload into a branded workspace
succeeds on both the sync and async paths). Combined total:
375/375 passing, verified 3 consecutive clean runs.

Initial-ship test breakdown (24 new tests): 11 on `BrandProfilePort`/
`SqliteBrandAdapter` (set/get roundtrip, never-set and wrong-owner
both return `None`, whole-record-replace semantics proven by showing
a second `set` call with fewer fields wipes the omitted ones rather
than preserving them, `created_at` survives updates while `updated_at`
advances, delete respects ownership, independent workspaces don't
leak into each other, `is_empty()` on both a fully-default and a
partially-set profile), 5 on prompt injection (brand fields present
in the prompt when set, absent when `None`, absent when present-but-
empty, only-the-set-fields appear — no placeholder text for unset
ones, and an end-to-end call with a brand profile still parses into a
normal `PresentationStrategy`), 8 HTTP-level (get-before-ever-set
returns 200 with blanks not 404, set-then-get roundtrip through the
real API, ownership enforced on all three brand endpoints, auth
required, delete reverts to the never-set state, and — the ones that
actually prove this doesn't break anything — generation into a
branded workspace succeeds, generation into an unbranded workspace is
unaffected, and the async job-payload serialize/reconstruct round
trip works end to end, not just the sync path). Full suite: 368/368
passing, verified 3 consecutive clean runs.

**Frontend, done same-session:** `api-client.ts` gained
`BrandProfile`/`getBrandProfile`/`setBrandProfile`/`deleteBrandProfile`.
The sidebar's expandable workspace folders (ADR-044) gained a "Brand
profile" toggle revealing a real inline form (5 plain text inputs —
name, colors, tone, audience, visual style — not a styled
color-picker or richer UI, matching this delivery's stated MVP scope
elsewhere) with Save/Clear, pre-filled from the real API on open.
Deliberately did NOT add a separate `/studio/brand` page — the
sidebar's existing (still-`comingSoon`) "Brand kits" nav item implies
a library/browse experience that isn't what got built; what shipped
is genuinely per-workspace inline editing, and mislabeling it as the
nav item's fuller concept would overstate the scope. Frontend
typechecks and builds clean.

*Next entry: ADR-046.*

## ADR-046 — Infographics: First Phase 6 Render Target

**Context:** v3 roadmap Phase 6 ("Infographics, diagrams, posters,
social graphics") — the first phase whose formats are genuinely
different render targets (SVG/HTML composition) rather than PPTX/DOCX
variants. The roadmap's own sequencing note said to build this first:
*"diagrams and infographics first — pure layout problems, no new
content-generation logic."* That held up exactly as predicted: this
entry required zero changes to Strategy, Outline Structure, Slide
Content, Layout Planning, or Quality Review — only a new `ExportPort`
adapter, the same shape of change ADR-041 (documents) made before it.

**Decision:** new `InfographicSvgExportAdapter`
(`backend/adapters/export/infographic_svg_adapter.py`, format_id
`infographic_svg`), registered in `registry._EXPORT_ADAPTERS`
alongside `pptx`/`document_docx`. Consumes the exact same `Recipe`
every other format does. No new endpoint, no new job type — the same
`export_format` string every generation endpoint already accepted now
also works for infographics, on both topic and document-upload
generation, sync and async, with no format-specific gating anywhere.

**Layout:** a single vertically-scrolling SVG — a title header (from
`slides[0]`, same "first slide becomes the header" convention
`document_docx_adapter.py` established) followed by one numbered card
per remaining slide, each with a heading and up to `MAX_BULLETS_
PER_CARD` (6) bullets. Colors come from `pptx_adapter.py`'s existing
`_COLOR_SETS` — deliberately NOT a separate infographic-only palette,
since the entire point of `Theme.color_set_id` existing is that one
theme choice should look consistent across every format a project
gets exported to, including brand-informed themes from ADR-045.

**A real bug caught by actually looking at the output, not just
passing tests:** the first version used a fixed `HEADER_HEIGHT`
constant, which left excessive dead space under short titles (a
one-line title still reserved room for three). All 13 initial tests
passed regardless, because none of them asserted anything about
whitespace proportions — this was only caught by rendering a realistic
sample to PNG (via `cairosvg`, a one-off dev-time check, not a new
project dependency) and visually inspecting it. Fixed by computing
header height dynamically from the actual wrapped title's line count
before laying out anything else. Worth remembering as a pattern: a
green test suite proves the assertions you wrote were satisfied, not
that the output looks right — for anything with a visual component,
actually rendering and looking at it once is cheap insurance a test
suite alone can't provide.

**SVG text doesn't auto-wrap**, so this does its own wrapping via
`textwrap.wrap` against an estimated average-character-width — not
real per-glyph font metrics. Stated explicitly as a deliberate
tradeoff in the module docstring: exact wrapping would need either a
real font-rendering dependency or shipping actual font metrics
tables, disproportionate for what's meant to be a fast, lightweight
visual summary rather than a typography-precise document.

**Status:** Accepted. 13 new adapter-level tests
(`tests/contract/test_infographic_svg_adapter.py`) — well-formed SVG
proven by actually parsing it with `xml.etree.ElementTree` (not just
"didn't raise"), title/section/bullet content present, one numbered
`<circle>` per section confirmed by count not just presence, long
bullet text genuinely wrapped (no single `<text>` line over 120
chars), bullets beyond the cap correctly dropped rather than growing
the card unboundedly, speaker notes never rendered, an empty outline
still producing valid SVG, different `color_set_id`s producing
genuinely different output (proving the theme actually flows through,
not hardcoded), and special characters (`&`, `<`, `>`, `"`) proven
escaped by parsing the result as XML rather than string-matching for
their presence. 4 new HTTP-level tests: sync, the bundling guard
correctly skipping this format, a full async round trip, and
document-upload mode targeting this format too. Full suite: 392/392
passing, verified 3 consecutive clean runs.

**Frontend, done same-session:** studio composer gained a third
`→ Infographic` toggle alongside Slides/Document. Went one step
further than the document format's UI: an actual inline `<img>`
preview renders directly in the chat thread, since browsers display
SVG natively and the job-download endpoint requires no auth — free to
add once the format existed. Typechecks and builds clean.

**Known gap, stated plainly:** the project editor
(`/projects/[id]`) only ever exports as PPTX regardless of what
format a project was originally generated as (`handleExport()` is
hardcoded to `"presentation.pptx"`). Editing a project's underlying
content there is genuinely useful for any format (same `Outline` model
underneath), but there's no re-export-as-infographic (or as-document)
button on that page yet — a real, if narrow, product gap left for a
future pass on that page specifically, not addressed here.

*Next entry: ADR-047.*

## ADR-047 — Diagrams: Second Phase 6 Render Target

**Context:** the second Phase 6 format per the roadmap's own priority
order ("diagrams and infographics first... posters and social
graphics second"). Where this entry earned its own design decision
rather than being a copy-paste of ADR-046: a "diagram" implies real
structure — sequence, branching, decision points — and the `Outline`
model (`models/recipe.py`) is a flat, ordered list of `Slide`s. It has
no representation of a decision point, a loop, or parallel branches at
all.

**Decision:** build the diagram type this data model can actually
support honestly — a linear process/sequence flow, one box per
section connected by arrows in slide order — rather than either (a)
silently ignoring structure the model doesn't have while visually
implying it does (a flowchart-shaped output that's incapable of
encoding an actual flowchart's branching is a dishonest artifact,
not a smaller version of a real one), or (b) inventing a new
structured branching input the AI pipeline would need to populate
(a materially bigger change — deferred to `V3_ROADMAP.md`, not
attempted speculatively here). This is the same "build what the data
honestly supports" reasoning ADR-041 already used once (document_docx
doesn't invent document-specific AI generation, it reuses the same
Outline verbatim) — applied here to a case where NOT doing so would
have been a more attractive shortcut, since a "flowchart" visually
reads as more sophisticated than it structurally is.

**Extracted `svg_utils.py`, a genuinely shared module** — the escape/
hex-color/text-wrap helpers `infographic_svg_adapter.py` (ADR-046)
already had were needed identically here, so they moved to a small
shared module rather than being duplicated a second time. Explicitly
NOT a shared layout engine or base class — `ExportPort`'s own
docstring principle ("a broken/slow adapter for one format never
affects the others") still holds; sharing pure, stateless string
utilities doesn't create the coupling that principle actually guards
against, duplicating character-escaping logic across every future SVG
adapter would just be a latent bug waiting to diverge between them.
`infographic_svg_adapter.py` was refactored to use the shared module
too — its own 13 tests re-run unchanged and still pass, confirming
the refactor was behavior-preserving.

**Each box** shows a section's title and, space permitting, only its
FIRST bullet as a terse sub-line — deliberately not a card of many
bullets like the infographic adapter's cards. A diagram box is meant
to read in a glance, not be read like a document; a dedicated test
confirms a second bullet on the same slide is correctly never shown,
not just that the first one appears. Same reused `_COLOR_SETS`
palette as every other format (ADR-046's reasoning applies
identically), same "slides[0] becomes the header" convention as
`document_docx_adapter.py` and `infographic_svg_adapter.py` before it.

**Verified visually before writing tests, learning directly from
ADR-046's own lesson** — rendered two realistic samples to PNG
(a normal 4-step onboarding flow, and a deliberately extreme long-
text edge case) and inspected both. The diagram adapter got the
layout right on the first attempt this time (no header-height-style
bug to fix), which is itself informative: computing header height
dynamically from wrapped-line count, the exact fix ADR-046 needed
partway through, was written into this adapter from the start instead
of being a bug to discover — direct evidence the earlier lesson
actually transferred rather than needing to be relearned.

**Status:** Accepted. 17 new adapter-level tests
(`tests/contract/test_diagram_svg_adapter.py`) — well-formed SVG via
real XML parsing, correct box count (verified by actual `<rect>`
count, accounting for the 2 non-box background/accent rects), exactly
N-1 arrows for N boxes (a single box produces zero arrows, confirmed
by a dedicated test, not just inferred from the N-1 formula), step
titles and the first-bullet subline both present, a second bullet on
the same slide confirmed absent (not just "first bullet present" —
the actual scoping-to-one behavior), a step with zero bullets still
rendering without a subline and without raising, speaker notes never
used as a subline, long titles genuinely wrapped, an empty outline
and a header-only (zero-step) outline both still producing valid SVG,
different color sets producing different output, and special
characters proven escaped by parsing as XML. 8 new tests for the
extracted `svg_utils.py` itself (escaping all 5 XML special
characters, hex formatting including single-digit-component padding,
wrapping short text unchanged, wrapping long text across multiple
lines, ellipsis truncation beyond max_lines, empty-string input
returning one empty line rather than raising). 4 new HTTP-level tests
(sync, bundling correctly skipped, async round trip, document-upload
mode). Full suite: 421/421 passing, verified 3 consecutive clean
runs.

**Frontend, done same-session:** studio composer gained a fourth
`→ Diagram` toggle. The result-card rendering logic in `studio/
page.tsx` was refactored from a stack of format-specific ternaries
(already getting hard to read at 3 formats) into a single
`FORMAT_CONFIG` lookup table keyed by `OutputFormat` — the diagram
format's inline SVG preview, download label, and section-count noun
("steps," distinct from infographic's "sections") all came from
adding one row to that table rather than another round of if/else
branches. Typechecks and builds clean.

**Carried-forward gap, unchanged from ADR-046:** the project editor
page still only ever exports as PPTX regardless of a project's
original format. Not addressed in this entry either — same stated
gap, not growing silently with each new format added.

*Next entry: ADR-048.*

## ADR-048 — Posters: Third and Final Phase 6 Render Target

**Context:** the last format in Phase 6's roadmap, and the one the
roadmap itself flagged as different from the other two: *"posters and
social graphics second — need real design-system work — this is where
frontend-design-grade visual judgment matters most and is worth doing
carefully rather than fast."* This entry took that seriously —
consulted this project's `frontend-design` skill before writing any
code, and it directly shaped two structural decisions, not just
surface styling.

**Decision, and why it looks different from ADR-046/047:**
1. **No numbered markers.** The infographic and diagram adapters both
   number their content because it genuinely IS ordered (a deck's
   slide sequence, a process's steps). A poster's highlight lines are
   independently true claims about the same topic, not a sequence —
   numbering them would be exactly the "decoration that doesn't encode
   real information" the skill warns against as a default AI-slop
   pattern. Verified by a dedicated test asserting no bare "1"/"2"/"3"
   text node appears anywhere in the output.
2. **The headline dominates**, per the skill's "the hero is a thesis."
   Where the other two adapters give the title a modest header
   treatment and spend most of the canvas on content, this adapter's
   title is the largest, boldest element on the page, with a
   restrained accent-circle signature device behind it — "spend your
   boldness in one place," not scattered decoration.

**Where this deliberately does NOT follow the skill as literally as a
bespoke page would:** color palette. The skill's guidance is one
considered, specific palette per brief. This reuses the same
`_COLOR_SETS` every other export format already uses (same reasoning
as ADR-046/047) — because this is a reusable engine serving arbitrary
topics via a small set of themes (including brand-informed themes
from ADR-045), not a one-off page; a user's chosen theme staying
consistent across every format they export to matters more here than
a bespoke one-off palette would per generation. Stated as a deliberate
tension with the skill's usual guidance, not an oversight.

**Two real bugs found by rendering and looking, not by the test
suite** — same discipline ADR-046 established, applied from the
start this time rather than learned mid-way through again:
1. Highlight lines had a small accent tick placed at each line's
   estimated left text edge — this project's `wrap_text` is a
   character-count estimate, not real font metrics (documented
   limitation, `svg_utils.py`), so the estimated edge didn't match
   where the actual centered text rendered, and the tick visibly
   overlapped the first line's text. Fixed by moving the tick to a
   small mark centered ABOVE each highlight block instead of beside
   it — centered elements don't need accurate width measurement to
   align correctly, sidestepping the root limitation entirely rather
   than trying to measure around it.
2. With a typical 3-highlight deck, content was pinned to a fixed
   top offset (mirroring the OTHER bug ADR-046 had to fix, not the
   same one) leaving the entire bottom half of the fixed-size canvas
   empty — looked broken, not minimal. Fixed by computing the whole
   content block's height first and vertically centering it within a
   safe band (clear of the top accent circles, clear of the footer),
   rather than starting layout from a constant.

**One remaining minor, stated limitation, not hidden:** an unusually
long 3-line headline can graze the decorative accent circles in the
poster's upper-right corner (verified by rendering a deliberately
extreme long-title case). Judged acceptable rather than fixed further
— the circles are low-opacity texture, not solid shapes, so text stays
legible where they overlap, and this is the one deliberate visual
risk the template already takes per its own docstring; chasing further
precision here traded against real returns for a corner case, not a
typical one.

**Also unlike the other two SVG adapters: a FIXED canvas** (800×1000,
a common portrait poster/social-graphic ratio), not one that grows
with content — a poster is meant to be one consistent shareable-image
size, confirmed by a dedicated test comparing a minimal-content and a
maximal-content poster's dimensions are identical. `MAX_HIGHLIGHTS`
(4) keeps content within what that fixed canvas can hold; a section
with no bullets falls back to its own title as the highlight (a
poster can't afford a dropped highlight just because a section lacked
supporting detail — its title is still a true claim about the topic).

**Status:** Accepted. 14 new adapter-level tests
(`tests/contract/test_poster_svg_adapter.py`) — well-formed SVG,
fixed canvas size regardless of content amount, headline present, no
numbered markers anywhere (the one behavioral difference from ADR-046/
047 actually verified, not just claimed), highlights correctly capped
at `MAX_HIGHLIGHTS`, a bulletless section falling back to its own
title, notes never used as a highlight, the divider present exactly
when there's at least one highlight and absent when there are zero
(both directions tested, not just the positive case), long headlines
genuinely wrapped, an empty outline still producing valid SVG,
different color sets producing different output, and special
characters proven escaped via real XML parsing. 4 new HTTP-level
tests (sync, bundling correctly skipped, async round trip, document-
upload mode). Full suite: 439/439 passing, verified 3 consecutive
clean runs.

**Phase 6 is now complete** — all three planned render targets
(infographics, diagrams, posters) shipped across ADR-046/047/048.

**Frontend, done same-session:** studio composer gained a fifth and
final `→ Poster` toggle. The `FORMAT_CONFIG` lookup table ADR-047
introduced specifically to avoid another round of stacked ternaries
did its job here — adding poster support was one new row, not a new
branch anywhere in the rendering logic. Typechecks and builds clean.

**Carried-forward gap, unchanged across all three Phase 6 entries:**
the project editor page still only ever exports as PPTX regardless of
a project's original format. Stated again rather than left to grow
silently invisible with each new format added — four formats deep now
(document, infographic, diagram, poster) and still not addressed
there.

*Next entry: ADR-049.*

## ADR-049 — Project Editor: All 5 Export Formats, Not Just PPTX

**Context:** the gap flagged and carried forward across all three
Phase 6 entries (ADR-046/047/048): the project editor page
(`/projects/[id]`) only ever exported as PPTX, regardless of a
project's actual format — real, narrow, and left explicitly stated
rather than allowed to grow silently invisible as more formats got
added. Four formats deep by the end of Phase 6, still unaddressed.
Closed this session before starting Phase 7.

**Decision:** the export button became a format selector + export
button pair. Every project's editor can now export to any of the 5
formats (`pptx`, `document_docx`, `infographic_svg`, `diagram_svg`,
`poster_svg`) — genuinely free to pick any of them regardless of
which format the project might originally have been generated as,
since every format is just a different `ExportPort` reading the exact
same `Recipe`/`Outline` (the same fact ADR-041/046/047/048 already
established makes this trivially true at the API level; this entry
is purely about the frontend finally exposing what the backend could
already do).

**Deliberately did NOT add "remember the project's original format"
as a smarter default.** `StoragePort`/`ProjectSummary` don't persist
which format a project was originally generated in — that's a real,
separate feature (a new stored field, a schema change) that would
need its own justification, not something to invent silently just to
make a dropdown's default marginally more convenient. The selector
defaults to `pptx` (matching the page's pre-existing behavior) and
is freely changeable from there.

**Extracted `lib/export-formats.ts`** — a small shared module (format
id, display label, short label for compact UI, file extension) so the
project editor and the studio composer read from one source of truth
for "which formats exist" rather than the editor introducing a THIRD
hand-maintained list of the same 5 format ids (studio's `FORMAT_CONFIG`
already existed from ADR-047, and was itself introduced specifically
to stop that duplication from spreading). The studio page's own
`OutputFormat` type alias was retired in favor of importing
`ExportFormat` from this shared module — one canonical type now, not
two type aliases for the identical five string literals that could
silently drift out of sync if a sixth format were ever added to one
but not the other. Studio's richer per-format UI config (icon,
download-button label, section-count noun) stayed local to
`studio/page.tsx`, since those are genuinely studio-specific
concerns, not something the editor page needs.

**Status:** Accepted. No new backend changes, no new backend tests —
this was purely a frontend surface change against an API that already
fully supported it (confirmed by the fact that zero backend files
needed touching). Verified: `npx tsc --noEmit` clean, `npm run build`
clean with `/projects/[id]`'s bundle size increasing as expected for
the new selector UI. Full backend suite re-run for completeness
despite being untouched: 439/439 passing, unaffected as expected.

*Next entry: ADR-050.*

## ADR-050 — Phase 7: Q&A on Uploaded Documents, and a Real-PDF Testing Gap Closed

**Context:** the last phase from the original vision doc's MVP scope
— "PDF Intelligence." The roadmap's own framing for this phase was
*"Document-mode already accepts PDFs for structure extraction. Extend
to Q&A-over-PDF... no new extraction logic needed, just new consumers
of what already exists."* Checked that "already accepts PDFs" claim
before building anything new, per this session's established
discipline of verifying rather than assuming — and found a real,
previously-invisible gap.

**A real gap found by checking, not assumed to be fine because the
roadmap said so:** every HTTP-level test that ever sent a `.pdf`
through the API used a deliberately CORRUPT one
(`test_generate_sync_corrupt_pdf_returns_422`) — a real, valid PDF
had never actually been sent through `/generate` and verified to
produce real output, for ANY of the 5 export formats, despite the
roadmap confidently stating PDF-to-any-format "already works." It
happened to be true (verified by manually constructing a real PDF and
running it through `generate_presentation()` for all 5 formats before
writing any test — same "render and look before trusting" discipline
ADR-046/048 established, applied here to a claim instead of a visual
layout), but "happened to be true, unverified" and "verified" are
different states, and the test suite only now proves the latter.

**No new PDF-generation dependency added** to prove this — this
project's only real PDF dependency is `pypdf` (for reading). Rather
than adding `reportlab` or similar just to generate a test fixture,
`tests/integration/test_api_http.py` gained a small hand-written
minimal-PDF constructor (`_make_minimal_pdf`) using raw PDF content-
stream syntax, round-tripped through `pypdf`'s own reader as proof it
produces genuinely valid, text-extractable output — zero new
dependencies, real coverage.

**The genuinely new feature: Q&A on an uploaded document.**
`AIPort` gained `answer_question(context, question) -> str` —
implemented identically across every real provider adapter (Gemini,
the OpenAI-compatible base shared by Groq/OpenRouter/HuggingFace,
LocalModel) via the same `_TextEnhancementMixin` pattern every other
AIPort text method already uses (`_answer_question_raising`,
wrapped by each adapter's public method in the established try/
except-degrade pattern), and cascades through `CompositeAIAdapter`
via the same generic `_cascade_text` every other method already
uses — no special-casing needed there at all.

**The one place this method's contract genuinely differs from every
other AIPort method, stated explicitly in the port docstring:**
`answer_question` has no meaningful non-AI degradation. Every other
AIPort method degrades to "return the input unchanged" when AI is
unavailable — a sensible fallback since presentations/documents/etc.
still work fine unenhanced. There's no equivalent sensible fallback
for "answer an arbitrary question about a document" — echoing the
question back, or the document's raw text, would both be actively
unhelpful, not a graceful degradation. So `NullAdapter.
answer_question` (and every adapter's degraded-path return, and
`CompositeAIAdapter`'s `degraded_default`) returns an explicit,
honest sentence stating AI isn't configured — never silence, never an
echo, verified by dedicated tests asserting the response is neither
the question nor the context verbatim.

**New endpoint: `POST /documents/ask`** — file upload + `question`
query param (matching the established convention every other file-
upload endpoint uses for its non-file parameters, confirmed by
checking existing passing tests' calling convention before writing
the new ones, rather than assuming). Reuses the exact same
`IngestionPort.extract_text` step every generation endpoint already
uses — genuinely "no new extraction logic," the one part of the
roadmap's framing that held up exactly as stated. Always returns
`200` with an `answer` field, even when AI isn't configured — the
HTTP layer follows the same "explicit honest message, not a special-
cased error" contract `AIPort.answer_question` itself establishes,
rather than inventing a `503` for a case the port already has a
defined behavior for.

**Gated by a SEPARATE, lighter quota bucket than generation
(`_enforce_qa_quota`, `_qa_limit_user`/`_qa_limit_anon`, env vars
`OPENPRESENT_DAILY_QA_LIMIT_USER`/`_ANON`, defaults 100/15 vs
generation's 30/5).** A single Q&A call is one AI request; a single
generation is 6+ (ADR-043's own reasoning for why generation's cap
exists at all). Sharing one bucket would make whichever cap got reused
wrong for the other feature. Refactored `_enforce_generation_quota`
into a small generic `_enforce_daily_quota` helper both quota gates
now call with different key prefixes/limits/nouns, rather than
duplicating the whole gate function a second time — verified
behavior-preserving by re-running the full suite before adding any
new tests (439/439, unchanged) immediately after that refactor, not
after the new feature was also mixed in.

**A real bug caught immediately, not shipped:** while wiring in the
new endpoint, a `str_replace` edit accidentally deleted the
`@app.get("/jobs/{job_id}")` decorator line entirely, silently
orphaning that route (the function still existed, just with no
route registered — FastAPI would 404 on the real endpoint while the
Python file still imported and ran without error). Caught immediately
by re-viewing the edited region right after making the change, before
running any tests — fixed before it could hide inside a "tests still
pass" false confidence (the existing test suite calling `GET /jobs/
{id}` would eventually have caught it too, but catching it by reading
the diff is strictly faster and doesn't rely on that route happening
to have test coverage).

**Status:** Accepted. 19 new tests: 4 on `NullAdapter`/
`LocalModelAdapter`'s `answer_question` (honest unavailable message
— explicitly not an echo of either the question or the context —
model response returned when available, degrades to an honest
message on server error, never surfaces a blank answer even when the
model itself returns one), 3 on `CompositeAIAdapter`'s cascade
(cascades to a working provider, degrades to the honest message when
every provider fails — not the generic "echo the input" every other
method's degrade uses — and behaves correctly with zero available
providers), 12 HTTP-level (real PDF through `/generate` for all 5
formats via `pytest.mark.parametrize`, `/documents/ask` requiring a
question, returning a real answer field via the `NullAdapter` path in
this hermetic suite, working with a real PDF specifically, correctly
rejecting an unsupported filetype and a corrupt PDF, and — proving
the separate-bucket design actually works rather than just being
described that way — a generation-quota env var set to 0 not blocking
Q&A, and Q&A's own limit genuinely blocking after being reached).
Full suite: 458/458 passing, verified 3 consecutive clean runs.

**This closes every phase from the original vision doc's MVP scope.**
Phases 1 through 7 are now all shipped, each with its honest, stated
partial gaps documented in `V3_ROADMAP.md` rather than glossed over.

*Next entry: ADR-051.*

## ADR-051 — Closing the MVP: Document Q&A Frontend

**Context:** ADR-050 shipped the Q&A backend, but explicitly flagged
(in its own delivery notes) that there was no frontend for it — a
user could not actually use the feature without `curl`. When asked to
"finish the final MVP so all the features mentioned can be deployed,"
this was the single most significant gap: a fully-built, fully-tested
backend feature with zero way for a real user to reach it. Closed
this session, no backend changes needed (confirmed by simulating the
exact request shape the new frontend code sends against the real
`/documents/ask` endpoint before considering this done — same
verify-before-trusting discipline as every prior delivery).

**Decision:** `askDocument(file, question)` added to `api-client.ts`,
following the same multipart-with-query-param pattern
`generateAsync` already established (file in `FormData`, `question`
as a URL query param — matching the convention every other upload
endpoint already uses, the exact same convention ADR-050 confirmed by
checking existing passing tests before assuming). Studio composer
gained a third input mode, "Ask a question about a document" —
distinct from the existing "Describe a topic" / "Upload a source
document" modes, since Q&A is a fundamentally different interaction
(question in, answer out; no job, no export format, no workspace
assignment) rather than another way to trigger generation. Its
composer UI is a two-part stacked layout (file picker row, then a
question textarea) rather than reusing the single-row composer box,
since ask mode is the one mode needing both a file AND free text at
once.

**Deliberately synchronous on the frontend, matching the backend's
actual contract** — no job creation, no polling, unlike every
generation mode. The answer appears as a normal assistant chat bubble
the moment the request resolves, since `POST /documents/ask` itself
is synchronous (one AI call, not 6+, per ADR-050's own reasoning for
why it has a separate, lighter quota bucket).

**Format toggles and the workspace selector are hidden in ask
mode** — both are meaningless for a feature that doesn't produce a
file or save a project, and showing them would silently invite a user
to wonder why picking "→ Poster" before asking a question does
nothing.

**One deliberate non-addition, reasoned through rather than defaulted
into:** the original vision doc listed "Summarize PDFs" as a distinct
capability alongside "Ask questions about PDFs." No separate
summarize button or endpoint was built — asking "Summarize this
document" as an ordinary question through the Q&A feature already
built produces exactly that outcome, since `answer_question`'s prompt
is generic Q&A grounded in the document, not restricted to narrow
factual lookups. A dedicated summarize affordance would duplicate a
capability that already exists under a more general one, not add a
missing one.

**Status:** Accepted. No new backend code, so no new backend tests —
verified instead by directly simulating the frontend's exact request
(file + `question` as a query param, matching `askDocument`'s real
implementation) against the live `/documents/ask` endpoint and
confirming a real `200` with the expected `NullAdapter` degradation
message, before considering the integration correct. Frontend:
`npx tsc --noEmit` clean, `npm run build` clean, `/studio`'s bundle
size increased modestly as expected for the new UI. Full backend
suite re-confirmed unaffected: 458/458 passing.

**This closes every user-facing gap called out across Phases 1-7.**
Every feature documented as shipped in `V3_ROADMAP.md` is now also
reachable by an actual person using the product, not just provable
via the API. Remaining stated gaps (brand-color-to-theme-token
mapping, workspace-level file storage) are deliberate, bounded scope
decisions, not missing UI on top of a finished backend.

*Next entry: ADR-052.*

## ADR-052 — A Real, Platform-Dependent Test Race Found on Windows

**Context:** you ran the full suite on your actual Windows deployment
machine (not this development sandbox, which is Linux) as part of
verifying the final MVP zip before deploying. `test_jobs_endpoint_
surfaces_stage_while_running` failed there — `assert body["stage"] ==
"building_outline"` got `"applying_design"` instead. This exact test
had passed on every run in this session's Linux sandbox, including
multiple explicit 3-5x repeated full-suite runs done specifically to
catch flakiness (the same discipline ADR-042 established after a
similar-shaped bug). It never reproduced there. It reproduced
immediately on your machine. Treated as a real bug to find and fix
properly, not dismissed as "just Windows being weird."

**Root cause, found by reading the actual code rather than guessing:**
the test's own comment claimed it was *"testing the /jobs/{id}
route's own response shape... not the worker's timing"* — true in
intent, false in what the code actually did. Every test using the
`client` fixture gets a real `TestClient(app)` with FastAPI's
lifespan-triggered in-process worker thread genuinely running in the
background (required for the many OTHER tests in this file that poll
real async jobs to completion). This test manually drove a job
through `QueuePort` by hand (`enqueue` → `dequeue` → `update_stage`)
to control its state directly — but that real background worker
thread, polling the exact same shared queue continuously, could also
see the freshly-enqueued job and race to dequeue and fully process it
for real before the test's own manual `dequeue()`/`update_stage()`
calls landed. When the worker won that race, it ran the actual
deterministic generation pipeline end to end, progressing the job's
`stage` through all 6 real values and landing on `"applying_design"`
(the last one before completion) by the time the test's HTTP request
fired — overwriting the test's manually-set `"building_outline"`
entirely. A genuine race, not corrupted state or a flaky assertion;
different OS thread-scheduling behavior between Linux and Windows is
a completely plausible, unremarkable reason the timing window that
makes the real worker win the race is far more reachable on one
platform than the other — not a reason to suspect the failure itself
was spurious.

**Decision:** new `client_no_worker` fixture in `tests/integration/
test_api_http.py` — identical to `client`, except it sets
`OPENPRESENT_INPROCESS_WORKER=false` before constructing the
`TestClient`, so no real background thread exists to race against a
test's manual queue manipulation. Scope checked before writing the
fix: `grep` confirmed exactly one test in the entire integration
suite manually drives `QueuePort` by hand
(`registry.get_queue_adapter()` + `enqueue`/`dequeue`/`update_stage`
all in the same test body) — so this fixture has exactly one
consumer, `test_jobs_endpoint_surfaces_stage_while_running`, switched
over to it. No other test needed touching; the other 457 either use
the real worker deliberately (polling real async jobs to completion)
or never touch the queue directly at all.

**Verification, not just "added a fixture and hoped":** ran the
fixed test in a **tight 15-iteration loop** before considering this
resolved (`for i in 1..15: pytest test_jobs_endpoint_surfaces_stage_
while_running`) — 15/15 clean, where the original code had just
failed on a real machine on what was presumably one ordinary run.
Then the full suite, 5 consecutive times — 458/458 every time,
matching this session's established "don't trust a single green run"
standard for anything touching threading/timing.

**Status:** Accepted. No behavior change to any production code —
this is a pure test-infrastructure fix. `docs/ARCHITECTURE_DECISIONS.
md` gets this entry specifically so a future session (or a future
`grep` for "race" or "flaky") finds the real story here instead of
re-discovering the same bug from scratch if it's ever touched again.
Full suite: 458/458 passing, verified 5 consecutive clean runs plus
15 consecutive clean runs of the specific fixed test.

*Next entry: ADR-053.*

## ADR-053 — Studio Experience Moved to the Site Root

**Context:** since Phase 1 (ADR-040), the new chat/sidebar/preview
experience deliberately lived at `/studio`, with the old v2
single-form generation page kept untouched at `/` — a conscious
choice at the time to build v3 incrementally without risking the
existing homepage. With every planned phase now shipped and the
product feature-complete, requested explicitly: make the real product
the actual main page, not a sub-route someone has to already know
about.

**Decision:** `frontend/app/studio/page.tsx`'s content moved to
`frontend/app/page.tsx` (the root route) wholesale. The old v2
homepage (a simple sync-generation form, `generateSync`/
`generateFromTopicSync`, no chat, no format choice beyond the
original PPTX/DOCX, no workspace or brand awareness) is retired — it
was always the predecessor UI the new experience was built to
replace, not a separate page worth preserving alongside it.

`/studio` itself is not deleted outright — it's now a one-line
server-side `redirect("/")`, so anyone with an old bookmark or
browser-history entry from testing this session lands somewhere real
instead of hitting a 404. `AppShell.tsx`'s routing condition (which
decides Sidebar-shell layout vs. the original NavBar layout) changed
from `pathname.startsWith("/studio")` to `pathname === "/" ||
pathname.startsWith("/studio")` — the root gets the full sidebar
experience now, the (now-trivial) `/studio` redirect route still
matches too so it never briefly flashes the wrong layout before
redirecting. `/login`, `/register`, `/dashboard`, and
`/projects/[id]` are entirely untouched — this move only affects
`/` and `/studio`.

`Sidebar.tsx`'s internal links updated to match: the logo/"Home" nav
item and "New presentation" button now point at `/` instead of
`/studio`; the still-`comingSoon` placeholder items (Templates, Brand
kits, Assets, Settings) were similarly repointed from `/studio/*` to
top-level paths for consistency, even though they're inert
(`onClick={e => e.preventDefault()}`) and don't currently navigate
anywhere — correctness now rather than a latent inconsistency waiting
to surface if they're ever enabled.

**Verified with real HTTP requests against the actual production
build, not just a successful compile:** ran `next build` then `next
start` and issued real requests — `GET /studio` returned a genuine
`307 Temporary Redirect`, and `GET /` returned `200` with the sidebar/
studio markup actually present in the returned HTML. A clean
`next build` alone would not have caught a redirect misconfiguration
or a routing condition that compiled fine but behaved wrong at
runtime — this is the same "run it and look, don't just trust the
build" discipline ADR-046/048 established for visual output, applied
here to routing behavior instead.

**Status:** Accepted. `npx tsc --noEmit` clean. `npm run build` clean,
with the route table itself confirming the intended shape: `/` at
102 kB (the full studio bundle) and `/studio` shrunk to 138 B (just
the redirect). No backend changes — this is a pure frontend routing
change. No new tests (this repo's frontend has no automated test
suite; verification here was the build + real HTTP requests against
the running production server, described above).

*Next entry: ADR-054.*

## ADR-054 — Content Actually Shaped for Its Format, Real Document
Design, and No More Watermarks

**Context:** direct, correct user feedback after living with the
product for a while: every generated file "looks like a deck but
with a different format," the design was mediocre, and every export
carried a "Generated with OpenPresent" watermark. All three were
real, not perception — this entry fixes all three, and in the
process finds and fixes four additional bugs that would have
undermined the fix if left alone.

**1. Watermarks removed.** "Generated with OpenPresent" deleted from
all three SVG adapters (infographic, diagram, poster) — it was never
present in PPTX/DOCX to begin with. `FOOTER_HEIGHT` constants kept
as reserved bottom margin (not deleted) so removing the text didn't
reintroduce cramped layouts. Regression tests added asserting the
text's absence explicitly, not just relying on nobody noticing it
was gone.

**2. Root cause of "looks like a deck": found in TWO separate code
paths, both fixed.**

*Path A — topic generation's AI pipeline.* `json_pipeline_base.py`'s
Content-stage prompt was hardcoded to demand "3-5 concise bullet
points... a single idea, not a paragraph," regardless of what format
the output would actually become. `GenerationRequest` gained an
`export_format` field (defaults to `"pptx"` — additive, every
unmigrated call site keeps its exact prior behavior) and
`_build_content_prompt` now branches: `document_docx` asks for 1-3
genuine multi-sentence prose paragraphs ending in terminal
punctuation; `infographic_svg`/`diagram_svg`/`poster_svg` ask for
short punchy standalone claims (visual-card content, explicitly not
slide bullets); `pptx` is unchanged.

*Path B — document-upload's rule-based extractor,* a completely
different mechanism producing the identical symptom: `rule_based.py`
(`StructurePort`) split ANY plain prose with no bullet markers on
sentence boundaries, one bullet per sentence — correct for a slide
deck, but shattering a source document's own real paragraphs into a
list that was never meant to be one. `StructurePort.build_outline`
and every downstream call (`_chunk_body`, `_slides_from_sections`,
`_known_shape_fallback`, `_minimal_slides_for_thin_content`) now
thread `export_format` through; for `document_docx` with no bullet
markers present, the whole section stays one connected paragraph.
Content genuinely authored as a list (real bullet markers in the
source) still splits per-item regardless of format — a real list
stays a real list in a document too.

**3. Two real bugs found while fixing Path A, before they could
undermine it.** MAX_BULLET_LENGTH (160 chars, sized for a slide-
bullet fragment) would have silently truncated real prose mid-
sentence, destroying the trailing punctuation the document renderer
depends on to detect "this is a paragraph, not a list item" — fixed
with a format-aware ceiling (1200 chars for document_docx,
unchanged elsewhere), verified with a test using a paragraph
deliberately long enough to have tripped the old limit. Separately,
`quality_validator.py`'s "paragraph-length bullet" and "layout
overflow risk" checks are deck-specific defects (a slide bullet
SHOULD be short; a scrolling Word document has no fixed layout
region to overflow) that would have flagged the new, correctly-
generated prose as a problem and fed it straight into the AI revision
pass — which would have dutifully shrunk it back into fragments,
silently undoing the whole fix. `validate_and_fix` gained the same
`export_format` parameter and skips both checks for `document_docx`;
tests prove the *same* input is flagged for `pptx` and not flagged
for `document_docx`, not just that document mode scores clean by
coincidence.

**4. Document design, fixed by actually rendering to PDF and looking
— not by trusting a green test suite, which had nothing to say about
any of this.** Two more real, independent bugs found this way, not
guessed at:
- The title page's "centered" heading was visually left-anchored.
  Root cause: python-docx's built-in `"Title"` style has a bottom-
  border box sized to the style's own fixed width, not the page or
  the actual centered text — confirmed by writing an isolated
  minimal test file and rendering it before touching the real code.
  Fixed by abandoning the built-in style for direct paragraph
  formatting: a real centered run plus a hand-built OOXML paragraph
  bottom border (`_set_bottom_border`) that spans the true page
  margins, exactly matching this project's own docx skill's guidance
  to use a paragraph border rather than a table for a horizontal
  rule.
- This adapter never used the project's theme at all — every
  document rendered in Word's stock blue heading color regardless of
  the chosen theme, unlike every other export format (pptx,
  infographic, diagram, poster), which have all consistently applied
  `_COLOR_SETS` since ADR-046. Now imports the same palette and
  applies real theme colors to the title and every section heading.
- Generalized `_should_run_as_paragraph` (singular, n=1 only) into
  `_all_read_as_prose` (any count): the new content prompt asks for
  1-3 *separate* paragraph-bullets per section, and the old
  single-bullet-only heuristic would have rendered multiple real
  paragraphs as a bulleted list of paragraph-length chunks — still
  deck-shaped, quietly defeating the entire point. Now: if every
  bullet in a section reads as a complete sentence, each one becomes
  its own real paragraph regardless of how many there are; the
  original single-bullet case is just the n=1 instance of this same
  rule, not a separate case anymore.

**Status:** Accepted. 26 new tests across 5 files: 3 watermark-
absence (one per SVG format), 8 on the format-aware content prompt
and truncation ceiling (document mode asks for prose, pptx keeps
bullets, visual formats ask for punchy claims, the default is
unchanged for unmigrated callers, long prose survives intact for
document mode, pptx keeps the original short ceiling), 6 on the
quality validator's format-aware skipping (both checks proven to
fire for pptx and not fire for document_docx on identical input, plus
the unset-format default), 4 on the structure adapter's prose-
preservation (stays one paragraph for document_docx, still splits
per-sentence for pptx, unset-format default unchanged, genuine
source lists still split per-item even for document_docx), and 6 on
the document adapter's design fixes (multiple paragraphs render as
multiple real paragraphs not a list, heading color matches the
theme, different themes produce genuinely different colors verified
by direct RGB comparison, a real OOXML paragraph border exists on
the title page checked at the XML level since python-docx has no
high-level getter for it, the title paragraph is genuinely centered,
title color matches the theme). Full suite: 484/484 passing, verified
3 consecutive clean runs. Three real sample documents were generated
and actually rendered to PDF via LibreOffice at each stage of this
fix (before, after the content-shape fix, after the design fix) and
visually inspected — this is what caught the border-box bug and the
missing-theme-color bug, neither of which any automated test would
have caught on its own.

*Next entry: ADR-055.*

---

## ADR-055 — Scope Narrowed to pptx / docx / pdf; Infographics, Diagrams, and Posters Removed

**Status:** Accepted.

**Decision:** `infographic_svg`, `diagram_svg`, and `poster_svg`
(ADR-046/047/048, v3 Phase 6) are removed as export formats. OpenPresent
now generates exactly three output formats: presentations (`.pptx`),
documents (`.docx`), and documents (`.pdf`). This is a deliberate
product scope decision, not a bug fix or a deprecation-for-technical-
reasons — the three SVG formats worked, had no open bugs, and had just
received the ADR-054 watermark-removal pass. They were cut because the
product's focus is narrowing, not because anything was wrong with them.

**What replaced them:** `document_pdf`, a new `ExportPort` adapter
(`DocumentPdfExportAdapter`, built on `reportlab`) that renders directly
from the same `Recipe`/`Outline` model every other format renders from
— there is no docx-to-PDF conversion step and no LibreOffice/soffice
dependency at runtime (soffice is still used, as before, only as a
*testing* tool to rasterize docx output for visual inspection per this
project's own "render and look" convention — see ADR-041/054). This
keeps the load-bearing architectural decision of the whole project
intact: one generation, N independent export adapters, a broken/slow
adapter for one format never affecting the others (ADR-011).

**Why a dedicated adapter instead of docx→PDF conversion:** a naive
"convert the docx to PDF" step would have made `document_pdf` a
second-class citizen of `document_docx` — dependent on it, unable to
diverge in design without also changing the Word output, and requiring
a LibreOffice binary in the production container at runtime (currently
only present in the dev/test image for the docx-skill's own visual-QA
tooling, not something this project has ever shipped to Render). A
direct, independent adapter avoids all three problems and matches how
every other format in this codebase already works.

**Content shape:** PDF is treated as a "document" for content-shaping
purposes, identically to `document_docx` — both now share the exact
same branch in `json_pipeline_base.py`'s content prompt (real 2-4
sentence prose paragraphs, not slide-bullet fragments) and the exact
same `document_docx`/`document_pdf`-aware skip logic in
`quality_validator.py` (the deck-specific "paragraph-length bullet" and
"overflow risk" checks are structurally meaningless for a flowing
document, whether it's rendered to `.docx` or `.pdf`) and
`rule_based.py`'s deterministic no-AI fallback. The two formats differ
*only* in the export/render step — never in what content gets
generated — exactly matching how `pptx` and `document_docx` already
relate to each other. Concretely: if this file changes, `document_pdf`
gets it too, automatically, with no separate maintenance.

**What was removed, precisely:**
- `backend/adapters/export/infographic_svg_adapter.py`,
  `diagram_svg_adapter.py`, `poster_svg_adapter.py`, and their shared
  `svg_utils.py`
- Their three format-branch entries in `registry.py`'s `_EXPORT_ADAPTERS`
- Their `_MEDIA_TYPES` / `_FILE_EXTENSIONS` / `_FILE_BASENAMES` entries
  in `api/main.py`
- The "punchy claims" content-prompt branch in `json_pipeline_base.py`
  that only those three formats used
- 4 contract test files (`test_infographic_svg_adapter.py`,
  `test_diagram_svg_adapter.py`, `test_poster_svg_adapter.py`,
  `test_svg_utils.py`) and the SVG-format cases inside
  `test_api_http.py` and `test_ai_pipeline_port.py`
- The three SVG format pills, `FORMAT_CONFIG` entries, and
  `EXPORT_FORMATS` entries in the frontend (`page.tsx`,
  `export-formats.ts`) — the project editor (`projects/[id]/page.tsx`)
  needed no changes at all, since it already reads format choices
  generically from the shared `EXPORT_FORMATS` table (ADR-049)

**What was added, precisely:**
- `backend/adapters/export/document_pdf_adapter.py`
  (`DocumentPdfExportAdapter`) — mirrors `document_docx_adapter.py`'s
  theme-aware title page and prose/list rendering logic line-for-line
  in intent (same `_all_read_as_prose` rule, kept as a literal copy
  rather than a shared import, to keep every export adapter
  independently self-contained per this project's existing
  convention — see that file's module docstring for the one accepted
  exception, `_COLOR_SETS`)
- `reportlab` added to `requirements.txt` (pure-Python, no system
  library dependency, unlike WeasyPrint)
- `"document_pdf"` entries throughout the same set of files listed
  above, plus a new `document_pdf` pill/config/format entry in the
  frontend
- `tests/contract/test_document_pdf_adapter.py` — mirrors
  `test_document_docx_adapter.py`'s cases (title-page centering and
  theme color, prose-vs-list detection, empty-outline handling,
  speaker-notes exclusion) using `pypdf` to extract text back out for
  assertions, since reportlab has no read-back API the way
  python-docx does

**Verification:** full backend suite green across 4 consecutive runs
(427/427 — down from 484 as expected: -18 removed SVG-format tests,
+13 new PDF-format tests, net -5 plus a few consolidated
parametrizations). A real sample document was generated end-to-end
with the `blue_academic` theme, rendered via `pdftoppm`, and visually
inspected on both pages: the title page shows a genuinely centered
title in the theme's title color with a full-width accent rule (no
reintroduction of the ADR-054 left-anchor bug), and the content page
shows correctly-distinguished real prose paragraphs (Executive
Summary) alongside a real bulleted list (Key Findings), both in the
theme's colors.

**Stated gap:** infographic/diagram/poster generation no longer
exists in this codebase at all — reintroducing any of them later
would mean writing a new adapter from scratch, not restoring removed
code from history, since this ADR treats their removal as deliberate
and permanent, not paused.

*Next entry: ADR-057.*

---

## ADR-056 — Studio Shell Frontend Gaps Closed: Collapsible Panels, Project Deletion, a Real Settings Page

**Status:** Accepted.

**Decision:** Five real, independently-reported frontend gaps in the
studio shell (`/`) are closed together, since three of them shared the
same root cause (a UI element existed but had no `onClick`/route/close
affordance behind it — decorative, not broken):

1. **Sidebar has no close button.** Added. `AppShell.tsx` now owns
   `sidebarOpen` state (persisted in `localStorage` under
   `op_sidebar_open`, so a closed sidebar stays closed across reloads
   within the studio shell) and renders a floating reopen button when
   collapsed. `Sidebar.tsx` takes an optional `onClose` prop and
   renders a close button next to the logo.

2. **Preview/Edit panel has no close button, and "Edit" was dead UI.**
   Both fixed together, since they're the same panel. The preview
   column now has a close (×) button and a slim reopen affordance when
   collapsed, mirroring the sidebar's pattern. Separately: "Edit" was
   previously a `<span>` with no `onClick` — clicking it did nothing.
   It's now a real link to the saved project's editor
   (`/projects/{id}`) once a generation resolves to a project, or a
   genuinely disabled state (not just visually inert) with a tooltip
   explaining why, when there's no project yet (anonymous generation,
   or still in progress). `JobBubblePreviewMirror` now takes an
   `onProjectId` callback to surface the resolved project id up to the
   panel that needs it for the link.

3. **No way to delete a previous chat (saved project).** This was a
   real gap in both layers, not just the frontend:
   `StoragePort.delete_recipe()` has existed since Phase 4 (used
   internally by workspace-delete's tests) but was never wired to an
   HTTP route, so there was no way to delete a project at all,
   frontend or otherwise. Added `DELETE /projects/{project_id}` (owner-
   scoped, 404 for both "doesn't exist" and "not yours" — same
   isolation contract as every other project route, existence is
   never leaked) and `deleteProject()` in `api-client.ts`. Delete
   (trash icon) buttons added everywhere a project is listed: the
   sidebar's Recent list, inside expanded workspaces, and the
   `/dashboard` project grid — three UI locations, one shared backend
   route and one shared frontend function.

4. **Settings does nothing.** The nav link previously called
   `preventDefault()` and did nothing at all — worse than not being
   there, since it looked clickable. `/settings` is now a real route.
   Deliberately kept small and, more importantly, **entirely
   functional** — nothing on the page is decorative:
   - Account email, via a new `GET /auth/me` route. This didn't exist
     before either — `/auth/login` only ever returned a bare session
     token, so the frontend had no way to answer "who am I logged in
     as" without decoding the (intentionally opaque, per
     `ports/auth.py`) token itself.
   - Sign out (reuses the existing `logout()`).
   - **Default output format** — a real preference, stored in
     `localStorage` under `op_default_export_format`, read once on
     mount by `app/page.tsx` and applied to the composer's format
     selection. Chosen over decorative "settings" (e.g. a fake theme
     toggle) specifically because it does something observable the
     next time the person opens a new chat.
   - Workspaces/brand profiles are explicitly *not* duplicated here —
     a one-line note points back to the sidebar, where they already
     live per-workspace (ADR-045). Settings pages that re-host
     functionality already available elsewhere tend to drift out of
     sync with the real thing; not doing that here was deliberate.

5. **"New presentation" renamed to "New."** One-line copy change in
   the sidebar's primary action button — the product generates three
   formats now (pptx/docx/pdf, ADR-055), so a button that only ever
   says "presentation" was stale copy left over from before that
   change, not a UI bug exactly, but worth fixing alongside everything
   else here.

**What was added, precisely:**
- Backend: `GET /auth/me`, `DELETE /projects/{project_id}` — both in
  `api/main.py`, no new port methods needed (`StoragePort.delete_recipe`
  already existed; `AuthPort` already returns `User(id, email)` from
  `get_user_from_session`).
- Frontend: `app/settings/page.tsx` (new). `AppShell.tsx` (sidebar
  open/close state). `Sidebar.tsx` (close button, delete buttons,
  Settings link enabled, "New" copy). `app/page.tsx` (preview panel
  close/reopen, working Edit tab, reads the default-format
  preference). `app/dashboard/page.tsx` (delete buttons). `lib/api-
  client.ts` (`getCurrentUser`, `deleteProject`). New CSS in
  `globals.css` for every new interactive element above.

**Verification:** full backend suite green across 4 consecutive runs
(435/435 — 427 from ADR-055 plus 8 new: 3 for `/auth/me`, 5 for
`DELETE /projects/{id}` including a per-owner-isolation test mirroring
the existing pattern for every other project route). Frontend:
`tsc --noEmit` clean, `next build` succeeds and now emits 9 static
routes (up from 8 — `/settings` is real now, not a dead link).

**Stated gap, left alone deliberately:** there is still no confirm-
before-navigate-away or undo for project deletion beyond the
`window.confirm()` dialog already used for workspace deletion (ADR-044)
— consistent with that existing pattern, not a new gap introduced
here. A styled confirmation modal (replacing every `window.confirm`/
`window.prompt` in the sidebar, not just this one) would be a real,
separate piece of work, not invented here just for this one button.

*Next entry: ADR-058.*

---

## ADR-057 — Q&A Feature Removed; One Consistent Shell for the Whole App; Real Slide Content in Preview

**Status:** Accepted.

**Decision:** Three more real, reported gaps closed together:

1. **Document Q&A ("Ask a question about a document") removed as a
   product feature**, a deliberate scope decision matching ADR-055's
   pattern, not a bug fix. `POST /documents/ask` and its dedicated
   quota bucket (`_enforce_qa_quota`, `_qa_limit_user`/`_qa_limit_anon`)
   are gone from `api/main.py`, along with the frontend's third
   composer mode (`Mode` is now just `"topic" | "document"`) and
   `askDocument()` from `api-client.ts`. **Stated, deliberate gap:**
   `AIPort.answer_question` and its implementation across every AI
   adapter (`local_model.py`, `openai_compatible_base.py`,
   `gemini_adapter.py`, `composite_adapter.py`, `null_adapter.py`,
   `json_pipeline_base.py`'s `_answer_question_raising`) are left in
   place — removing a port method touches every adapter file for a
   codepath nothing calls anymore, which is real, separate work from
   closing the one frontend-reachable gap that was actually reported.
   If document Q&A comes back later, or the port method's removal
   becomes worth doing on its own, that's new work, not a revert.

2. **One consistent shell for the whole app**, closing what "clicking
   Recent/Settings/Edit/Sign out sends me to the old page" actually
   was: `/dashboard`, `/settings`, and `/projects/[id]` never got the
   Claude-style sidebar shell that `/` got in ADR-053 — they still
   rendered inside the original pre-redesign `NavBar`/plain-page
   layout. Every link into those routes from inside the sidebar
   (Recent, Settings, Edit) genuinely did drop the person into a
   different, older-looking product, which is exactly what it looked
   like from the outside. `AppShell.tsx`'s `isStudioShell` check now
   covers those three routes too — they keep the sidebar, just with
   different content in the main panel. `/login` and `/register`
   deliberately keep the plain layout (a centered auth form doesn't
   need a sidebar with nothing meaningful to show yet). Settings'
   sign-out now redirects to `/` instead of `/login` — logging out
   should return you to the app in its logged-out state, not force an
   immediate login prompt. The sidebar's "Recent presentations" label
   is shortened to "Recent" (product generates 3 formats, not just
   presentations — same reasoning as ADR-056's "New" rename, just a
   spot that edit missed).

3. **Collapsed-sidebar button was visually "misplaced."** Root cause:
   it was a `position: absolute` floating overlay (ADR-056), which
   sits ON TOP of whatever's underneath rather than making room for
   itself — exactly the kind of thing that reads as misplaced once
   real page content is behind it (this became visible once fix #2
   above put real content on more routes behind it). Replaced with
   `.op-sidebar-collapsed`, a slim 48px strip that's part of the
   normal flex row alongside `.op-shell-content`, the same way the
   full-width sidebar already is. No more overlap possible by
   construction, not by tuning z-index/position values.

**Also closed — reported together, same investigation:**

4. **"New presentation" hardcoded text.** ADR-056's rename covered the
   sidebar's primary button and the sidebar's Recent-list label but
   missed a static `op-chat-header` div at the top of a fresh chat —
   now "New chat".

5. **Preview appeared twice (chatbox and preview/edit tab), and neither
   one actually showed what the deck looks like** — both true and both
   the same root cause. `JobBubble` (the chat-thread message) and
   `JobBubblePreviewMirror` (the right-hand panel) each independently
   rendered their own title-only slide grid from the same data.
   Fixed by:
   - Removing the slide grid from `JobBubble` entirely — the chat
     message now only confirms the result (icon, "ready", section
     count, download/edit actions), never duplicating what the panel
     right next to it already shows.
   - `GET /projects/{id}` now returns each slide's `bullets` (notes
     excluded — see the route's own docstring for why that has to
     match what every export adapter already does) and the project's
     `theme.color_set_id`, not just `order`/`title`. This is what
     "can't really see what the deck looks like without downloading"
     needed: titles alone were never going to answer that question,
     regardless of how they were laid out.
   - `JobBubblePreviewMirror` renders real cards — title, up to 3 real
     bullet lines, theme-colored border/background/accent — instead of
     a grid of title-only chips. `THEME_COLORS` in `page.tsx` is a
     small, deliberate frontend copy of backend `pptx_adapter.py`'s
     `_COLOR_SETS` (title/accent/background only) rather than a shared
     source of truth across the language boundary; if a color set is
     ever added on the backend, it needs adding here too — not a
     silent gap, an explicit, documented duplication.
   This is still a content preview, not a pixel-accurate render of the
   exported file (no fonts/layout/images match the real .pptx/.docx/
   .pdf) — a real visual renderer is a genuinely different, much larger
   piece of work than this fix, not attempted here.

**Verification:** full backend suite green across 4 consecutive runs
(430/430 — 428 from removing 7 Q&A tests off ADR-056's 435, plus 2 new
tests for the `bullets`/`theme` fields on `GET /projects/{id}`).
Frontend: `tsc --noEmit` clean, `next build` succeeds (still 9 routes —
no routes added or removed this time, only what renders inside them).
