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

*Next entry: ADR-029.*
