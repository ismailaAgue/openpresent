# OpenPresent — Technical Blueprint (Full 13-Section Version)

*No code. Architecture and design decisions only.*
*Every choice below states: why it was chosen, its cost impact, and how it could be replaced later without a rewrite.*

---

## 1. System Architecture

**Design:** Two independent runtime layers connected by a queue, with every external dependency (AI, storage, export, media) behind a port/interface — as established in the prior blueprint. Layer 1 (web) is CDN-served and stateless. Layer 2 (generation) is a queue-fed worker pool.

**Why:** A crash or slowdown in generation must never take down the marketing site, dashboard, or auth — these are your SEO/ad-revenue surface and must stay up regardless of load elsewhere. Decoupling is the only way to guarantee that structurally, not just by convention.

**Cost impact:** Layer 1 stays free at any traffic level (CDN edge caching absorbs it). Layer 2 is the only layer whose cost grows with usage — isolating it means you only ever pay for the part of the system that actually needs paying for.

**Future replacement options:** The queue can move from a database table to a managed queue service without touching either layer's internal logic, since both only ever call `enqueue()`/`dequeue()`. Layer 1's hosting provider can change (Cloudflare → any other CDN/edge platform) without affecting Layer 2 at all, and vice versa.

**Amendment — browser-side processing as a stated principle, scoped deliberately.** Per architect review: prefer client-side (browser) computation over server computation wherever it doesn't compromise security or output consistency. In practice this means:
- **Client-side (adopt):** live editing state, theme/layout preview while a student adjusts a slide, UI-level validation, draft autosave to local state before committing to the server.
- **Server-side (retain, do not move):** document parsing (the untrusted-input security boundary from Section 11 depends on controlled, consistent server-side handling), final PPTX/PDF/DOCX rendering (must produce identical output regardless of the student's device — a phone browser and an old school computer must not render differently).

**Why the boundary is drawn here, not further:** the cost and responsiveness win from browser-side work is real for anything interactive and low-stakes; moving parsing or export client-side would trade a real security containment guarantee and cross-device consistency for a marginal cost saving on work that's already cheap server-side (rendering is not the dominant cost line per the earlier cost board — AI and queue capacity are). The amendment is adopted where it clearly helps; it is not extended past that point.

---

## 2. Frontend Architecture

**Design:** Next.js, split into two rendering strategies within one app —
- **Static/SSG:** landing pages, blog, tutorials, template gallery, docs (pre-rendered, CDN-cached, near-zero server cost per view).
- **Client-rendered:** the editor, dashboard, and generation flow (interactive, needs live state).

**Why Next.js specifically:** built-in SSG/CDN-friendly output solves the Layer 1 cost problem directly; strong i18n routing support matters given the language-system requirement (Section 8); large ecosystem means less custom tooling to maintain solo.

**Component structure:** a thin `app/` routing layer, a `components/` library shared between static and dynamic pages, and a single `lib/api-client` module that's the *only* place frontend code talks to the backend — this keeps the API contract in one place, so backend changes touch one file, not scattered fetch calls.

**State management:** local component state plus a lightweight global store only for session/auth and the in-progress editor recipe — deliberately not adding a heavy state library (Redux, etc.) unless the editor's complexity later demands it.

**Cost impact:** static pages cost effectively $0 to serve at any scale (this is most of your traffic, per the earlier cost board). Only the interactive app pages consume real compute, and that's minimal (client-side rendering, thin API calls).

**Future replacement options:** the static/dynamic split means the marketing site could theoretically move to a different framework entirely later without touching the app; the `api-client` abstraction means swapping how the frontend talks to the backend (REST → GraphQL, etc.) is a single-file change.

---

## 3. Backend Architecture

**Design:** FastAPI, organized by port, not by generic "controllers" — each of the nine ports from the prior blueprint (Ingestion, Structure, AI, Design, Export, Storage, Media, Queue, Notification) is its own Python module with a defined interface (abstract base class or Protocol) and a folder of adapters implementing it.

**Why this organization, not a typical MVC layout:** MVC groups code by technical role (controller/model/view); porting by *capability* means "replace the export engine" or "add a new AI provider" touches exactly one folder, never several scattered files. This directly serves the "replaceable components" constraint at the code-organization level, not just the architecture-diagram level.

**API design:** a small set of REST endpoints — submit job, check job status, fetch/save recipe, list projects, auth. Deliberately minimal; the complexity lives inside the ports, not in a sprawling API surface.

**Auth:** simple email/session-based auth at launch (no third-party dependency required, keeps cost at $0); designed as its own port so OAuth or a managed auth provider can be added later without restructuring anything else.

**Cost impact:** FastAPI runs comfortably on the cheapest VPS tier or serverless functions at low traffic; async support means one small server can handle meaningful concurrent load before any scaling spend is needed.

**Future replacement options:** because ports are Python interfaces, not framework-specific code, the core logic could theoretically move to a different backend framework later with the port implementations largely intact — the framework is a thin shell around the real architecture, not the architecture itself.

---

## 4. Database Schema

**Design (conceptual, not DDL yet):**

- `users` — id, email, auth fields, created_at
- `projects` — id, owner_id, source_text, audience_type, language, created_at, updated_at
- `versions` — id, project_id, label, created_at
- `outlines` — id, version_id, structure_source (rule-based | ai-enhanced)
- `slides` — id, outline_id, order, title, content_blocks (JSON), media_refs (JSON)
- `themes` — id, version_id, layout_template_id, color_set_id, font_set_id
- `export_history` — id, version_id, format, generated_at, expired (boolean) — **metadata only**
- `jobs` — id, project_id, type, status, created_at, started_at, completed_at, error (nullable)
- `media_assets` — id, owner_id, storage_ref, type, compressed (boolean), created_at

**Why this shape:** mirrors the "recipe, not files" principle exactly — the schema stores structured, regenerable data, and nothing here scales with export volume, only with project volume, which is inherently smaller and slower-growing.

**Why relational (not document/NoSQL):** the data is genuinely relational (projects have versions, versions have outlines and slides, slides reference media) — a relational schema gets you referential integrity for free, and PostgreSQL's JSON column support handles the semi-structured parts (content_blocks) without needing a separate NoSQL system to maintain.

**Cost impact:** *Amended per architect review.* Free-tier managed PostgreSQL (e.g. Supabase, Neon) costs the same as SQLite at launch — $0 — while removing an entire future migration step. **Decision: use managed Postgres from day one**, not SQLite-then-migrate. This was a case where the original "cheapest possible" instinct and the "avoid future rework" constraint pointed to different answers at zero cost difference, so the constraint wins.

**Future replacement options:** scaling Postgres itself (read replicas, connection pooling, sharding by owner_id) are all additive changes to this same schema, not restructuring. No migration path is needed since the target database is the launch database.

---

## 5. Presentation Recipe Format

**Design:** a versioned JSON structure, the canonical representation of a project's content and structure — this is the actual "recipe" referenced throughout the strategy documents.

```
{
  "recipe_version": "1.0",
  "project_id": "...",
  "source_text": "...",
  "audience_type": "student_school",
  "language": "en",
  "outline": {
    "structure_source": "rule-based" | "ai-enhanced",
    "slides": [
      {
        "order": 1,
        "title": "...",
        "content_blocks": [
          { "type": "bullet", "text": "..." },
          { "type": "note", "text": "..." },
          { "type": "media", "ref": "media_asset_id" }
        ]
      }
    ]
  },
  "theme": {
    "layout_template_id": "...",
    "color_set_id": "...",
    "font_set_id": "..."
  }
}
```

**Why a versioned, explicit schema field (`recipe_version`):** this is the single most important detail for long-term flexibility — it means the recipe format itself can evolve (new block types, new theme fields) without breaking old projects, because the export engine and editor can branch on version and migrate old recipes forward deliberately, rather than the schema being an implicit, fragile assumption baked into code.

**Cost impact:** none directly — this is a data format, not infrastructure — but indirectly, a stable, well-versioned format is what makes "regenerate on export" cheap and safe long-term, since it's the only thing that needs to be stored and it compresses to almost nothing (plain text/JSON).

**Future replacement options:** new content block types (charts, tables, embedded video later) are additive fields, not breaking changes. A future format version could add fields for collaboration metadata (owner per slide, from the original vision's Section 4) without disrupting existing projects.

---

## 6. Template System Design

**Design:** templates are **data, not code** — a `layout_templates` table/config (grid definitions, placeholder positions, text-flow rules) and a `theme_sets` table/config (color palettes, font pairings) that the rule-based Design Engine reads and applies. Templates are versioned assets, not hardcoded logic paths.

**Why data-driven, not code-driven templates:** this is what lets you add a new template or theme without touching the Design Engine's code at all — a designer (even non-technical, later) could add a new layout by adding a new JSON/config entry, not by shipping a code change. It also means templates can be tested, previewed, and rolled back independently of application releases.

**Structure:** a small library of layout *archetypes* (title slide, bullet-list slide, two-column, image-focus, quote/callout) combined orthogonally with theme *tokens* (colors, fonts, spacing scale) — this combinatorial approach gives many visual outcomes from a small, maintainable set of building blocks, rather than needing to hand-design every layout/theme combination individually.

**Cost impact:** zero runtime cost — template application is fast, deterministic computation, not AI inference, consistent with keeping the Design Engine fully rule-based per the Constitution.

**Future replacement options:** the archetype+token model scales cleanly to adding institutional branding (Premium feature from the strategy doc) later — a school's branded theme is just a new token set, not a new engine.

---

## 7. Export Engine Design

**Design:** one Export Port, three adapters at launch — PPTX (`python-pptx`), PDF (headless browser rendering of an HTML representation, or ReportLab), DOCX (`python-docx`). Each adapter takes a finished recipe (post-Design Engine) and renders it into its target format independently.

**Why headless-HTML-to-PDF over a pure PDF library:** rendering the same layout logic that produces the visual slide (likely HTML/CSS-based internally, given the Design Engine's output) through a browser renderer keeps visual consistency between formats without duplicating layout logic per format — reduces long-term maintenance burden significantly for a solo builder.

**Why synchronous rendering happens inside the async worker, not the API request:** export is CPU-bound work; doing it inside a queued worker job (Section 5 of the prior blueprint's request flow) rather than a live HTTP request is what keeps Layer 1 unaffected by rendering load, directly serving the "website never crashes from generation load" principle.

**Cost impact:** rendering is CPU time, not a metered API call — cost is purely compute, which is the cheapest resource type to scale horizontally (add more worker instances) compared to a paid-per-call service.

**Future replacement options:** each format adapter can be swapped independently — e.g., moving from ReportLab to a different PDF renderer touches only that one adapter. Adding a new export format (HTML export, mentioned as future in the original vision) is a new adapter, not a redesign.

---

## 8. Language System Design

**Design:** three distinct, independently-scoped layers of "language," per the Constitution's emphasis that this isn't just UI translation:

1. **UI strings** — standard i18n (Next.js i18n routing + a string dictionary per locale).
2. **Narrative structure conventions** — the Structure Engine's rule library (Section 3.2 of the prior blueprint) can have language/culture-specific variants of "known narrative shapes," since presentation conventions aren't identical across languages/regions.
3. **Content generation/rewriting** — when AI is enabled, the AI Port's prompts are language-aware; when AI is off, content stays in the source document's original language (the rule-based path doesn't translate, only structures — an honest, explicit limitation worth stating rather than overpromising).

**Why separating these three layers explicitly:** conflating them (treating "language support" as one feature) is how projects end up promising more than the rule-based engine can actually deliver — translation genuinely requires AI or a translation service; structuring and UI don't. This separation keeps the "AI optional" promise honest per-layer instead of vaguely applied to "languages" as a whole.

**Cost impact:** UI and structural language support are free (static dictionaries, rule variants). Only true content translation would ever require AI/translation-API cost — and per this design, that's clearly scoped as an optional enhancement, not a baseline requirement.

**Future replacement options:** each new supported language is additive — a new locale dictionary, a new (optional) narrative-shape ruleset. No architectural change needed to go from 2 languages to 10.

---

## 9. Media Handling Architecture

**Design:** a Media Port with two adapters — **user uploads** (local processing: validate, compress, store) and **external stock media** (proxy to an external provider's API, never permanently cached, per the Constitution's explicit "no large media database" principle).

**Why never caching external stock media:** avoids both a storage cost that grows unboundedly and any licensing/rights complexity that would come from OpenPresent hosting third-party stock content itself — the external provider remains the source of truth and the licensor.

**Upload flow:** validate file type/size at the API boundary before it ever reaches processing (security boundary, Section 11) → compress/optimize → store via the Storage Port → reference by ID in the recipe's `media_refs`, never embedded directly.

**Cost impact:** compression before storage keeps the Storage Port's footprint small regardless of what students upload; not caching stock media means that line item never grows with usage at all.

**Future replacement options:** the external stock adapter can be swapped to a different provider, or multiple providers added behind the same port, without touching upload handling. Video support (explicitly deferred in the strategy doc) is a new adapter added later, not a redesign of this port.

---

## 10. AI Plugin Architecture

**Design:** the AI Port from the prior blueprint, formalized as a true plugin system — a defined interface (`propose_structure(outline, source_text) -> outline`, `rewrite(text, instructions) -> text`, `translate(text, target_lang) -> text` — each a separate, optional capability, not one monolithic "call AI" method) with adapters registered via configuration, not code changes.

**Why capability-scoped methods instead of one generic AI call:** lets each capability degrade independently — structuring can be AI-enhanced while translation stays disabled, for instance — and makes the `NullAdapter` trivially correct for each (each method just returns the unmodified input).

**Capacity check pattern:** before any AI call, the port checks a lightweight capacity/availability signal (queue depth, provider health) and short-circuits to the null behavior if unavailable — this is what makes "AI pauses, generation continues" (Constitution Principle 3) an enforced architectural behavior, not just a hoped-for outcome under load.

**Cost impact:** with `LocalModelAdapter` as default and `HostedAPIAdapter` present but disabled, routine cost is $0; the capacity-check pattern means even under a demand spike, the system's default behavior is to degrade gracefully to zero-cost operation rather than silently running up an API bill.

**Future replacement options:** adding a new AI capability (e.g., speaker-notes generation, mentioned in the original vision) is a new method on the same port pattern. Swapping which local model runs, or which hosted provider is the emergency fallback, is configuration, not code.

**Amendment — AI roadmap expanded beyond structure improvement, per architect review.** The AI Port's capability set is confirmed as: `propose_structure`, `rewrite`, `translate`, `summarize`, `suggest` — matching the Constitution's full list, not narrowed to structuring alone. Each remains independently optional and independently null-adaptable, so expanding the roadmap doesn't weaken the "AI pauses, generation continues" guarantee — it just means more capabilities can each individually degrade to a no-op under load, rather than only one. Phase 2 (Section 13) is updated to build these together rather than sequencing structure-improvement alone first.

---

## 11. Security Architecture

**Design, by boundary:**
- **Upload boundary (Document Ingestion, Media Port):** strict file-type allowlisting, size limits, and parsing in a constrained context before any content reaches the rest of the system.
- **AI boundary (AI Port):** receives only pre-extracted, pre-sanitized text and performs only narrow, defined operations — never raw file access, never free-form instruction-following from document content, which contains and limits prompt-injection risk at the architectural level rather than relying solely on filtering.
- **Data boundary (Storage Port):** every query scoped by `owner_id` at the interface layer, not left to individual endpoints to remember — this is the difference between "we have a security policy" and "the architecture makes the insecure version impossible to accidentally write."
- **Abuse boundary (Queue/API Gateway):** rate limiting and bot-pattern detection sit in front of the queue, so abusive traffic is filtered before it ever consumes a worker slot, protecting both uptime and the fair-usage promise for real students.
- **Temp file boundary:** expiry is a scheduled system property (a cleanup job), not something each export path has to remember to trigger.

**Why boundary-based, not feature-based security:** security added per-feature tends to have gaps wherever a developer forgets; security enforced at the port/interface level applies uniformly to every current and future adapter automatically.

**Cost impact:** minimal — rate limiting and validation are cheap checks; the real cost-avoidance benefit is indirect (abuse prevention protects the compute budget the AI Port and worker pool depend on).

**Future replacement options:** stronger auth (OAuth, 2FA) can be layered onto the existing auth port later; more sophisticated bot detection can replace the launch-stage simple rate limiter without touching anything downstream.

---

## 12. Deployment Strategy

Directly extends the staged cost table already validated in the prior blueprint (Section 6) — restated here as deployment decisions:

- **Stage 0–1 (0–10K users):** single cheap VPS or free-tier serverless functions for the API, free-tier managed Postgres (per amendment 1 — no SQLite stage), local open-source inference engine (Ollama or equivalent — the specific engine is an adapter choice, not an architectural commitment) on the same or a second cheap machine, CDN (Cloudflare) for Layer 1. Total infra cost: near $0.
- **Stage 2 (10K–50K):** managed Postgres (single instance), managed lightweight queue, small autoscaling worker pool for generation. `HostedAPIAdapter` configured but left off by default.
- **Stage 3–4 (50K–1M+):** autoscaling worker pool sized to queue depth, Postgres with read replicas if data volume warrants it, full monitoring/alerting on queue length and cost-per-generation.

**Why staged rather than "build for scale from day one":** every stage transition is triggered by observed load (queue depth, cost-per-generation crossing a threshold), not a calendar date or a hope — this avoids both under-provisioning (crashes) and over-provisioning (wasted solo time/money on capacity you don't have traffic for yet).

**Config-driven environments:** which adapters are active (which AI adapter, which storage backend, which queue implementation) is environment configuration, not separate code branches — the same codebase runs unmodified from Stage 0 through Stage 4, only its configuration changes. This is the direct payoff of the ports/adapters architecture applied to deployment, not just code structure.

**Cost impact:** summarized fully in the earlier cost board; nothing here changes those figures, this section just specifies *how* each stage is actually deployed to hit them.

**Future replacement options:** hosting provider itself (VPS vendor, serverless platform) can change at any stage without touching application code, since nothing in the architecture assumes a specific provider's proprietary features.

---

## 13. Development Phases

Matches the phase plan already agreed, now explicitly tied to the ports built in each phase:

**Phase 0 — Foundation:** repo scaffold, empty Layer 1/Layer 2 skeletons, managed PostgreSQL (free tier) with the Section 4 schema, no functioning ports yet.

**Phase 1 — Prove the core thesis (zero AI):** build Document Ingestion, rule-based Structure Engine, Design/Theme Engine, Export Port (PPTX + PDF), Storage Port (recipe + temp file). AI Port present only as `NullAdapter`. **Milestone: a student can upload a document and download a real, well-designed deck, with $0 AI cost.**

**Phase 2 — Add AI where it earns its keep:** implement `LocalModelAdapter` covering the full capability set (`propose_structure`, `rewrite`, `translate`, `summarize`, `suggest` — per amendment 3), wire the capacity-check pattern for each capability independently, add the Queue Port for real async processing. **Milestone: same flow, better output when AI is available, identical fallback when it isn't, for every AI capability independently.**

**Phase 3 — Make it usable for real students:** auth, project/version dashboard, minimal editor, Notification Port (polling is enough at this stage). Quiet launch to 20–50 real students.

**Phase 4 — Only after Phase 3 validates the loop:** content/SEO pages (Layer 1 static content), project-reuse (new Version generation from an existing recipe), Stage 2+ deployment scaling as real traffic demands it.

**Why this order specifically:** it front-loads the highest-risk assumption (can a rule-based engine alone produce something genuinely usable?) into Phase 1, before any AI or infrastructure investment — if Phase 1's output isn't good enough on its own, that's critical information to have before Phase 2 onward, not after.

---

## Did This Take the Constitution Into Account?

Yes — explicitly, section by section:

- **Business Model** (free-first, AdSense-primary, no subscriptions for students, institutional licensing as a separate track) shaped the deployment cost targets in Section 12 and the media/storage cost-avoidance decisions in Sections 6 and 9 — the whole architecture is built to keep per-user cost low enough that ad revenue alone can sustain it at the traffic levels discussed earlier.
- **Cost Optimization** principles (recipe-not-files, generate-only-on-export, no permanent stock media storage, minimal logging) are implemented directly in Sections 4, 5, 7, and 9 — not just referenced, but built into the schema and port designs themselves.
- **Features** (student wedge scope, free unlimited creation with no credit wall, multilingual priority, tutorials for SEO) shaped Section 8's three-layer language design and Section 2's static/dynamic frontend split, which exists specifically to serve the tutorial/SEO content cheaply.
- **Technical Principles** (software before AI, AI optional, free AI only, store recipes not presentations, generate only when needed) are the direct source of Sections 5, 6, 7, and 10 — the recipe format, the rule-based-first Design Engine, the Export-on-demand pattern, and the AI Port's capability-scoped, capacity-checked design all exist specifically because of these principles, not as generic best practices layered on top.

**Resolved:** the earlier open deviation (AI Port scoped to structure-improvement only) has been closed per architect review — Phase 2 now builds the full Constitution-aligned capability set together. No open deviations remain between this blueprint and the Constitution as of this revision.

---

## 14. Plugin Architecture

**Design:** every *optional* capability — AI, Export formats, Themes, Templates, Stock Media providers, and any future integration — is implemented as a plugin: a registered adapter behind its Port, enabled or disabled via configuration, discoverable through a plugin registry rather than hardcoded into the core application.

**The guarantee this adds, beyond the existing ports/adapters pattern:** ports/adapters already made components *replaceable*. This principle adds a stronger, testable property — **removing a plugin must never affect the rest of the application.** A disabled AI plugin, a removed export format, an unregistered stock-media provider: none of these should require touching core logic, and none should be able to break a code path outside their own boundary. This is deliberately stricter than "swappable" — it's "subtractable with zero blast radius."

**Why this matters over a multi-year timeline:** the Constitution's own framing — presentations today, other communication formats eventually — means the plugin surface will keep growing (new export formats, new AI capabilities, new integrations not yet imagined). Without an explicit plugin discipline, that growth tends to leak into the core over time even with good intentions. Naming it as a first-class principle, with a registry and an enable/disable mechanism, keeps that growth contained by construction rather than by vigilance.

**Cost impact:** none directly — this is an organizing principle for code, not infrastructure. Its payoff is reduced long-term maintenance cost: adding, removing, or replacing any optional capability is a scoped, low-risk change rather than a cross-cutting one.

**Future replacement options:** this is itself the mechanism that makes future replacement cheap everywhere else in the system — it's the general case that Sections 3.3 (AI Port), 3.5 (Export Port), and 3.7 (Media Port) already each implement as specific instances.

## 16. Cost Ceiling & Circuit Breaker System

**Context, stated plainly by the founder:** OpenPresent has no budget and no revenue yet. Survival depends entirely on cost control holding even at large scale — not as an aspiration, but as a mechanism the architecture enforces on its own, since a solo founder cannot be the real-time safety check.

**Design:** cost control is elevated from "a set of good design decisions" (recipe storage, rule-based default, staged deployment) to an explicit, self-enforcing subsystem with five components:

**16.1 — Automatic circuit breaker.** A defined spend ceiling (daily and monthly) is monitored continuously. Crossing it triggers automatic, staged degradation — disable `HostedAPIAdapter` → throttle non-essential AI capabilities → fall back further toward the pure rule-based path (Path A, Section 5 of the prior blueprint) — with no manual intervention required. This is a hard requirement, not a dashboard alert: the system must be incapable of silently overspending while unattended.

**16.2 — Input deduplication/caching.** Structurally similar submissions (hashed on normalized input) can reuse prior AI-enhanced outlines rather than recomputing from scratch. This is a real, audience-specific lever: student submissions cluster by curriculum and assignment type, unlike a general-purpose tool's traffic — reuse (with appropriate variation, never verbatim duplication of another student's output) is a legitimate cost optimization here, not just a generic caching trick.

**16.3 — Batch inference.** The Queue Port (Section 3.8, prior blueprint) is designed to support batching waiting jobs into a single inference call where the underlying model/provider supports it, rather than always processing one job per call. Per-unit inference cost drops meaningfully under batching on both self-hosted and API-based models.

**16.4 — Preemptible/spot compute for workers.** The existing retry/dead-letter job handling (already required for reliability) is what makes spot/preemptible compute viable for the worker pool — a job that can be safely retried on a different instance tolerates preemption. This connects a reliability decision directly to a major cost lever.

**16.5 — Cost-per-generation as a live, continuous metric.** Not just a deployment-stage trigger (Section 12) — it feeds the circuit breaker (16.1) in real time, so the system always knows its own unit economics, not just at scheduled checkpoints.

**Why this is architecture, not policy:** every mechanism above is something the system does automatically, by construction — the founder's stated survival requirement doesn't depend on anyone remembering to check a dashboard, especially given the $0-budget, solo-operator reality this project starts from.

**Cost impact:** this section has no cost itself; its entire purpose is bounding the cost of everything else in the system, with a hard, automatic ceiling rather than a best-effort target.

**Future replacement options:** each mechanism (16.1–16.5) is independently tunable via configuration (ceiling values, dedup similarity threshold, batch size, spot vs on-demand ratio) without touching core logic — consistent with every other cost-sensitive decision in this blueprint.

---

---

## 17. Governance

Two process rules adopted per architect review, effective immediately:

**17.1 — `ARCHITECTURE_DECISIONS.md`**
A running log of significant design decisions, maintained alongside this blueprint (see companion file). Each entry records: the decision, the context that prompted it, why it was chosen over alternatives, its cost impact, and its status (accepted / superseded). This exists so future decisions are checked against *documented reasoning*, not memory — and so a decision can be revisited deliberately (superseded with a new entry) rather than silently drifting.

**17.2 — Cost-impact rule for new features**
From this point forward, no feature is added to the roadmap without an explicit statement of its cost impact — infrastructure cost, AI cost if applicable, and storage cost — following the same why/cost/replaceability format used throughout this blueprint. This turns the Cost Optimization document from a one-time analysis into a standing checkpoint every future decision passes through.

**Going forward, every implementation decision is checked against, in order: the Constitution → this Technical Blueprint → the Cost Optimization document → `ARCHITECTURE_DECISIONS.md`.** Where any of these conflict, the conflict itself is logged as a new ADR entry and resolved deliberately, not silently.
