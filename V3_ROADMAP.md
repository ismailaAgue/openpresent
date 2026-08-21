# OpenPresent v3 — Roadmap & Architecture Notes

Status: **Phase 1 shipped** (this delivery) = new Claude-style studio
frontend, wired to your real, already-deployed backend. Everything
below Phase 1 is backend work that doesn't exist yet — scoped and
sequenced, not built.

---

## Phase 1 — shipped in this zip

- `frontend/app/studio/page.tsx` — new chat-driven generation screen:
  left column is a message thread (topic or document mode), right
  column is a live preview panel. Matches the reference screenshot's
  layout (sidebar + chat + preview/edit tabs).
- `frontend/components/Sidebar.tsx` — Claude Code–style left rail:
  logo, "New presentation," nav, recent projects (real data via
  `listProjects()`), account/sign-out.
- `frontend/components/AppShell.tsx` — routes `/studio/*` into the new
  full-height shell; every existing page (`/`, `/dashboard`, `/login`,
  `/projects/[id]`) is untouched and keeps working exactly as before.
- New `--op-*` design tokens in `globals.css` (violet→blue gradient
  from your logo), additive only — nothing from the v2 "desk lamp"
  theme was removed.
- `public/logo.png` — your uploaded mark, resized for web use.
- **Everything here calls your real endpoints** (`generateFromTopicAsync`,
  `generateAsync`, `getJobStatus`, `getProject`, `jobDownloadUrl`).
  There is no mock data. The one honest simplification: the backend's
  job-status endpoint only reports `pending/running/done/failed`, not
  which of the 5 real pipeline stages is active — so the step chips
  animate on a timer while `running`, not from live per-stage
  telemetry. If you want real per-stage status, that's a small,
  well-scoped backend addition (see Phase 2).

**To apply:** unzip `frontend/` over your existing `frontend/` folder
(it only adds/replaces the files listed above — nothing in `backend/`
touched), then `npm install && npm run build` and deploy as usual.

---

## Phase 2 — make the chat interface tell the truth in real time

Small, high-leverage backend change: have the worker write a
`current_stage` field onto the job record as it moves through
Strategy → Outline → Content → Layout → Review, and return it from
`GET /jobs/{id}`. This turns the studio's step chips from
"plausible timer animation" into an accurate live status, and is a
prerequisite for a real chat-style multi-turn interface later (see
Phase 5).

## Phase 3 — Documents, as a second output type

Reuse the existing 5-stage AI pipeline and Null-adapter architecture:
- New `document` recipe in `backend/recipes/` (proposals, exec
  summaries, reports) sharing Strategy/Outline/Content stages with
  presentations; only Layout/Export differ (DOCX via python-docx
  instead of PPTX).
- Add a `format` selector to the studio composer (`Presentation` /
  `Document`), same chat flow, same job/project model — `projects`
  table gains a `kind` column (`presentation` | `document`).
- This is the highest-leverage next step: it's mostly plumbing, not
  new AI design, because your ports/adapters pipeline already
  generalizes past slides.

## Phase 4 — Project Workspace (the vision doc's "central experience")

- Promote `projects` from "one deck" to "one folder of assets + brand
  profile," per the vision doc's Section on Project Workspace.
  Concretely: a `workspaces` table owning N `projects` (each a
  presentation, document, or later an infographic/poster), plus
  `workspace_files` for uploaded source material.
- Sidebar's "Projects" section (currently a flat recent-list) becomes
  real folders once this lands — the UI already has the visual slot
  for it.

## Phase 5 — Brand Memory

- `brand_profiles` table: colors, tone, audience, visual direction,
  keyed to a workspace. Inject as a system-prompt fragment into every
  Strategy-stage call for that workspace, and as literal theme tokens
  into the Layout stage. This is additive to the existing pipeline
  (one more input, not a new stage) — low risk, high perceived value.

## Phase 6 — Infographics, diagrams, posters, social graphics

- These are genuinely different render targets (SVG/HTML composition,
  not PPTX/DOCX), so they get their own export adapter each, but
  should still consume the same Strategy/Content stages where
  possible (e.g., an infographic is "Content stage output rendered as
  an SVG layout" more than it's a new AI concept).
- Recommend building these in this priority order, each cheap given
  the shared pipeline: **diagrams and infographics first** (pure
  layout problems, no new content-generation logic), **posters and
  social graphics second** (need real design-system work — this is
  where `frontend-design`-grade visual judgment matters most and is
  worth doing carefully rather than fast).

## Phase 7 — PDF Intelligence (as an input, expanded)

Document-mode already accepts PDFs for structure extraction. Extend
to Q&A-over-PDF and "convert PDF into X" by keeping the existing
extraction step and routing its output into whichever recipe (Phase 3
document, Phase 6 infographic, existing presentation) the user picks
in the studio's mode selector — no new extraction logic needed, just
new consumers of what already exists.

---

## Cross-cutting: cost circuit breaker

Your handoff doc already flags this as the top real risk (§5): a
single generation is 6+ AI calls, and every phase above adds more
surface for that. Before Phase 3 ships, add a per-user/per-workspace
generation cap (simple counter + `429` once exceeded) — this is a
half-day task now and a much more painful one to retrofit once
documents/infographics/posters are all live and each burning calls
independently.

---

## What I did *not* invent

No new database tables, migrations, or backend endpoints were created
in this delivery — only frontend code calling endpoints that already
exist and are already deployed. Every number, status value, and field
name used in `studio/page.tsx` (`pending/running/done/failed`,
`X-Project-Id`, `getProject().slides`, etc.) was read directly from
your real `backend/ports/queue.py` and `lib/api-client.ts`, not
guessed.
