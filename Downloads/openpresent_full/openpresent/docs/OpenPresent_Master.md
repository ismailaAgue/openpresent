# OpenPresent — Master Reference

*Consolidated for the GitHub repository. This file combines: Constitution, Business Model, Cost Optimization, Features, Roadmap, Technical Principles, Technical Blueprint, and Architecture Decisions — reflecting the current, final agreed state of the project (rule-based-first architecture, student wedge, AdSense-primary monetization, cost-governed scaling).*

*Companion files in this repo: `TECHNICAL_BLUEPRINT.md` and `ARCHITECTURE_DECISIONS.md` are the canonical, frozen versions of Sections 7–8 below — treat those as source of truth if this file and those ever diverge after future edits.*

---
---

# 1. Constitution

**Principle 1 — Software before AI.** If a problem can be solved with software rules, templates, and algorithms, do not use AI. AI is an enhancement, never a requirement.

**Principle 2 — AI is optional, everywhere.** The presentation generator must always work without AI. When AI is enabled, it improves structuring, writing, rewriting, translation, summaries, and suggestions — but every one of these degrades gracefully to a rule-based or pass-through result when AI is unavailable, at capacity, or disabled.

**Principle 3 — Free AI only, by default.** OpenPresent does not depend on paid AI APIs for normal operation. AI sources are free, open-source, or self-hosted models. A paid API adapter may exist in the architecture as a deliberate, switched-off emergency lever — never a routine dependency. If AI capacity is unavailable, AI features pause; presentation generation continues.

**Principle 4 — Store recipes, not presentations.** OpenPresent does not permanently store generated PPTX, PDF, or DOCX files. It stores structure, text, themes, and layout instructions — the "recipe." The presentation is regenerated on demand.

**Principle 5 — Generate only when needed.** No unnecessary computation. Edits are saved to the recipe; files are generated only on export.

**Principle 6 — The free version provides real value, uncapped in kind.** Students never see a credit counter, a "generations remaining" badge, or a paywall interrupt for normal use. Daily volume limits that reflect real compute cost are legitimate backend safeguards against abuse — they are never surfaced to the user as a visible limit, and they never block normal student usage.

**Principle 7 — Premium exists only where justified.** Premium features exist only when justified by real infrastructure cost or professional/organizational need (e.g., institutional licensing) — never as a lever against the core student audience, and never built before the free product's core differentiator works well.

**Principle 8 — Users own their work.**

**Principle 9 — Never depend on one provider.** Not for AI, not for hosting, not for any external adapter.

**Principle 10 — Build globally.** Architecture supports language support from the start; full localization is added as real usage justifies it.

**Principle 11 — Projects remain editable and reusable.** A project is a reusable knowledge asset, not a one-time export.

**Principle 12 — Quality over feature quantity.** A fully working, narrow pipeline beats a half-working general one.

**Principle 13 — Codebase remains private.** Community feedback is welcome.

**Principle 14 — Every feature must strengthen the competitive advantage,** not be added because a competitor has it.

**Principle 15 — Ship the smallest version of the real differentiator before the largest version of the commodity feature.** Reuse before collaboration. One wedge before general-purpose. Rule-based baseline before AI enhancement.

**Principle 16 — Every optional capability is pluggable.** AI, Export, Themes, Templates, Stock Media, and future integrations each communicate only through a defined Port. Removing a plugin must never affect the rest of the application.

**Principle 17 — Cost survival is architecture, not vigilance.** Cost control mechanisms (circuit breakers, deduplication, batching, spot compute) are automatic and self-enforcing — the system must be incapable of silently overspending while unattended, since a solo, $0-budget operator cannot be the real-time safety check.

**Principle 18 — Every new feature states its cost impact before it's added,** following a consistent why / cost / replaceability format, checked against this Constitution and the documents below, in order, before implementation.

---

# 2. Business Model

**Audience:** students — school and university presentations (class assignments, project presentations, thesis/defense talks, seminar presentations, group projects). Not general-purpose, not investor pitches.

**Core promise:** free, unlimited presentation creation for students, with no subscriptions, no credit systems, and no visible usage limits — ever, for normal use. This is the product's actual competitive wedge against Gamma, Tome, and Beautiful.ai, all of which gate usage behind credits or trials.

**Primary monetization: AdSense.** Non-intrusive placement only (homepage, tutorials, template library, SEO content) — never inside the generation flow, never blocking export. Because students are the audience, volume is the lever, not per-user price. SEO content aimed at high-frequency, recurring student search intent is core product work, on par with the generation pipeline itself.

**Revenue expectation is realistic, not optimistic.** AdSense RPM for this niche realistically sits around $2–6, depressed further by high ad-blocker adoption among students. Reaching $5,000/month personal income requires roughly 200,000–400,000 monthly active users — a multi-year, content-compounding goal, not a fast path. Individual student subscriptions are explicitly rejected: they would directly contradict the reason the project exists for its actual audience.

**Known, permanent revenue gaps, planned for rather than fought:** ad-blocker users, and regions where AdSense doesn't serve ads (e.g., Russia, where Google has permanently ceased ad serving and monetization since 2022). These users still contribute traffic, SEO signal, and word-of-mouth value even without direct ad revenue — financial planning should assume a discounted monetizable share of total MAU, not 100%. Acceptable, non-coercive mitigations: a dismissible "support us / whitelist us" prompt, an optional direct-support channel (e.g., Buy Me a Coffee), and ad-network diversification/mediation. Never: blocking access, degrading the core product, or attempting to technically defeat ad blockers.

**Optional adjacent revenue:** institutional licensing (a school or university pays for a branded/bulk-managed deployment) — kept strictly separate from the individual student promise, evaluated only once the core product and its traffic are real.

**Cost governance is tied directly to the business model, not set arbitrarily:**
- **Pre-revenue:** infrastructure spend ceiling of **$0–20/month**, achievable entirely on free tiers plus local hardware.
- **Post-revenue:** infrastructure spend ceiling of **20–25% of trailing 30-day ad revenue**, recalculated continuously and enforced by the automatic circuit breaker (Section 7 / Technical Blueprint Section 16). This scales safely with the business at every stage without needing to be manually re-set.
- **Per-user AI safeguard:** a generous, invisible daily quota on *AI-enhanced* generation specifically (not on presentation creation itself). Exceeding it never blocks a student — it simply falls back to the free, unlimited, rule-based path, keeping "unlimited presentations, always" literally true.

---

# 3. Cost Optimization

**The central insight the whole architecture is built around:** the AI generation and queue/worker layer is the only cost line that scales meaningfully with usage. The website, database, and storage layers can be kept near-zero cost at any scale through the decisions below — so cost discipline concentrates almost entirely on one part of the system.

**Website:** static pages, CDN-served, minimal servers. Target: near-zero cost at any traffic level, since this layer is decoupled from generation load entirely.

**Database:** store users, projects, recipes, and settings. Avoid storing generated files or unnecessary history.

**Storage:** generated files (PPTX/PDF/DOCX) are temporary — generate, allow download, delete after a short window. Only the recipe persists long-term.

**Images/media:** user uploads are compressed and optimized before storage. Stock images are proxied from external providers, never permanently cached or stored.

**Templates:** store reusable components (title blocks, charts, layouts, themes) as data, not hundreds of complete presentations.

**Monitoring:** track only errors, uptime, queue length, and failures. Delete unnecessary logs. Cost-per-generation is tracked continuously as a first-class metric, not just at deployment-stage checkpoints.

**Five additional cost-control mechanisms, formalized as an automatic subsystem (see Technical Blueprint Section 16):**
1. **Automatic circuit breaker** — a spend ceiling (see Business Model, Section 2) that, when crossed, automatically degrades AI usage in stages, with no manual intervention required.
2. **Input deduplication/caching** — structurally similar student submissions (clustered by curriculum) can reuse prior AI-enhanced outlines rather than recomputing from scratch.
3. **Batch inference** — queued jobs are processed in batches where the underlying model/provider supports it, reducing per-unit inference cost.
4. **Preemptible/spot compute** for generation workers, enabled by the existing retry/dead-letter job handling that reliability already requires.
5. **Cost-per-generation as a live, continuous metric** feeding the circuit breaker in real time.

**Estimated infrastructure cost by scale** (see Technical Blueprint Section 12 for the full staged breakdown):

| Monthly active users | Estimated infrastructure cost/month |
|---|---|
| 0–1,000 | $0–10 |
| 1,000–10,000 | $10–30 |
| 10,000–50,000 | $50–150 |
| 50,000–200,000 | $200–600 |
| 200,000–1,000,000+ | Roughly $600–3,700, bounded by the circuit breaker regardless of actual demand |

**Every deployment stage transition is triggered by observed data (queue depth, cost-per-generation crossing a threshold) — never by a calendar date or a traffic projection.**

---

# 4. Features

**Core (free, unlimited, no credit wall):**
- AI-optional presentation generation from an uploaded document (essay, notes, research text)
- Rule-based automatic design: layouts, typography, spacing, alignment, slide hierarchy, themes — always available, never AI-dependent
- Editing: fonts, sizes, colors, spacing, layouts, slide order
- Export: PPTX, PDF (DOCX and image export as the export engine matures)
- User-uploaded images and logos, compressed and optimized
- External stock media (proxied, not stored)
- Language support: UI translation, structural narrative conventions, and (optional, AI-dependent) content translation — treated as three distinct layers, not one feature
- Tutorials and guides built into the site — serve users, SEO, and ad revenue simultaneously

**Optional AI enhancement (never required):**
- Outline/structure improvement over the rule-based baseline
- Rewriting, translation, summarization, suggestions
- Each capability independently degrades to a no-op when AI is disabled or at capacity — never an error, never a block

**Deliberately delayed, not abandoned:**
- Real-time collaboration (Stage 3 — a genuinely different, multi-person engineering effort)
- Enterprise administration/permissions
- Private AI deployment for institutions
- Marketplace
- Presentation types beyond the student wedge
- Languages beyond the first 1–2 targeted at launch
- AI image generation, video upload, offline version

---

# 5. Roadmap

**Phase 0 — Foundation.** Repo scaffold, empty web/generation layer skeletons, managed PostgreSQL (free tier) with the core schema. No functioning capabilities yet.

**Phase 1 — Prove the core thesis, zero AI cost.** Document ingestion, rule-based structure engine, rule-based design/theme engine, export (PPTX + PDF), recipe + temp-file storage. AI present only as a no-op adapter. **Milestone: a student uploads a document and downloads a real, well-designed deck, at $0 AI cost.** This is the highest-risk assumption in the whole plan, front-loaded deliberately: if a rule-based engine alone can't produce something genuinely usable, that's critical to know before any further investment.

**Phase 2 — Add AI where it earns its keep.** Full AI capability set (structure, rewrite, translate, summarize, suggest) via a self-hosted model, capacity-checked and independently gracefully-degrading per capability. Real async queue. **Milestone: same flow, better output when AI is available, identical fallback when it isn't.**

**Phase 3 — Make it real for actual students.** Auth, project/version dashboard, minimal editor, job notification. Quiet launch to 20–50 real students (a class, a Discord, a subreddit) before any public or SEO push — this is where the core loop gets tested against real usage before scaling effort.

**Phase 4 — Only after Phase 3 validates the loop.** Content/SEO engine (tutorials, subject- and grade-specific long-tail pages — the actual revenue driver), project-reuse (regenerate a project as a different format/version), staged infrastructure scaling as real traffic and revenue justify each step.

**Distribution, in parallel with Phase 4 and beyond:** direct channels first (student subreddits, Discord servers, campus groups) for fast real signal; long-tail SEO content compounding over 12–24+ months as the primary sustainable growth engine; institutional/B2B licensing explored only once the core product and traffic are proven.

---

# 6. Technical Principles

- **Ports and adapters, strictly applied.** Every external dependency (AI, storage, export, media, queue) sits behind a defined interface; a concrete provider is just one swappable adapter, never a hard dependency.
- **Two independent runtime layers.** The web layer (site, dashboard, auth) is CDN-served and must never go down because the generation layer (parsing, structuring, export) is under load. Async queue is the buffer between them.
- **Recipe, not files.** Persistent storage holds structured, regenerable project data. Generated files are disposable artifacts, not the source of truth.
- **Rule-based is the default, AI is the enhancement.** The rule-based path must be genuinely good on its own, not a degraded fallback — AI can only make it better, never required for a usable result.
- **Browser-side processing, scoped deliberately.** Client-side computation is preferred for interactive, low-stakes work (editing, preview, autosave). Document parsing and final export rendering stay server-side, to preserve the security containment boundary and guarantee identical output across devices.
- **Every optional capability is a plugin,** discoverable and configurable, removable with zero effect on the rest of the system.
- **Cost control is automatic, not procedural.** Circuit breakers, deduplication, batching, and spot compute are architectural mechanisms, not dashboard habits.
- **Every deployment stage transition is evidence-triggered,** never scheduled or anticipatory.
- **Security is boundary-based, not feature-based** — enforced uniformly at the port/interface level (upload validation, AI input sanitization, per-owner data isolation, rate limiting, temp-file expiry) so it applies automatically to every current and future adapter.
- **Decisions are logged, not just made.** Significant architectural choices are recorded in `ARCHITECTURE_DECISIONS.md` with why, cost impact, and alternatives considered — changes supersede prior entries rather than silently rewriting history.

---
---

# 7. Technical Blueprint

*The following is the full, current content of `TECHNICAL_BLUEPRINT.md`. See that file directly in the repository for the canonical, frozen version.*



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

---
---

# 8. Architecture Decisions

*The following is the full, current content of `ARCHITECTURE_DECISIONS.md`. See that file directly in the repository for the canonical, frozen version.*


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

*Next entry: ADR-013, reserved for the first Phase 1 implementation decision.*
