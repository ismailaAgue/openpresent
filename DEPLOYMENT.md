# Deploying OpenPresent — AI-First, Full Build (ADR-028/029/030)

Stack: **Render** (backend API + in-process worker), **Vercel**
(Next.js frontend), **Neon** (managed Postgres). Every step below is
explicit — exact URLs, exact env var names, exact commands to run,
exact JSON to expect back. Nothing is assumed.

This deploys: the 5-stage AI pipeline (Planner/Strategy → Outline →
Content → AI-driven Layout Planning → Quality Review), a 5-provider AI
fallback ladder (local → Gemini → Groq → OpenRouter → HuggingFace), a
4-provider image system (Unsplash/Pexels/Pixabay/Wikimedia) with
relevance scoring and dedup, a research stage that merges facts across
multiple providers (on by default), PPTX+DOCX
speaker-notes bundling, and optional Sentry monitoring.

---

## 0. What you need before you start

Nothing below is required to deploy — every one of these is optional,
and the app runs on $0 with zero keys configured (deterministic
fallback path). But each key you add turns on a real capability.
Gather whichever you want now; you can add the rest later without
redeploying code, just env vars.

| # | What | Where to get it | Free tier | Enables |
|---|---|---|---|---|
| 1 | Gemini API key | aistudio.google.com -> "Get API key" | Yes, generous | Default AI provider |
| 2 | Groq API key | console.groq.com/keys | Yes | AI fallback #2 |
| 3 | OpenRouter API key | openrouter.ai/keys | Yes (":free" models) | AI fallback #3 |
| 4 | HuggingFace token | huggingface.co/settings/tokens | Yes | AI fallback #4 |
| 5 | Unsplash access key | unsplash.com/developers | 50 req/hr | Image provider #1 |
| 6 | Pexels API key | pexels.com/api | 200 req/hr | Image provider #2 |
| 7 | Pixabay API key | pixabay.com/api/docs | 5000 req/hr | Image provider #3 |
| 8 | Tavily API key | tavily.com | Yes | Research provider #1 (best quality) |
| 9 | Brave Search API key | brave.com/search/api | Yes | Research provider #2 |
| 10 | Bugsink DSN (Sentry-protocol-compatible; a hosted or self-hosted Sentry/GlitchTip DSN also works, no code change) | bugsink.com -> sign up -> New Project -> Python | Yes, hosted plan (higher event quota than most alternatives) | Structured error monitoring |

Wikipedia needs **no key** and is on by default -- research works out
of the box, Tavily/Brave are quality upgrades, not requirements.

Wikimedia Commons needs **no key** -- it's always on as the universal
image fallback unless you explicitly disable it.

If you already have a Render/Vercel/Neon setup from a previous
deploy, skip straight to **Step 2, "If you already have the Render
service set up"** below and just add the new env vars.

---

## 1. Neon Postgres

**If you already have a Neon project attached: skip this step.**
`DATABASE_URL` doesn't change with this build -- no schema changes.

If setting up fresh:

1. Go to neon.tech -> **New Project**.
2. Pick a region close to where your Render service will run (reduces
   per-request latency).
3. On the project dashboard, copy the **connection string** -- it
   looks like `postgresql://user:password@ep-xxxx.region.aws.neon.tech/dbname?sslmode=require`.
   Use the **pooled** connection string if Neon offers both (better
   for a web service with concurrent requests).
4. Keep this string -- you'll paste it into Render as `DATABASE_URL`
   in Step 2.

---

## 2. Render (backend API + worker)

### If you already have the Render web service set up:

Go to your service -> **Environment** tab -> add whichever of the
variables below you want, using the exact names in the table. Then
**Manual Deploy -> Deploy latest commit** (or push to your watched
branch).

### If setting up the Render service fresh:

1. Push this codebase to your GitHub repo (`ismailaAgue/openpresent`
   or your fork/branch) if you haven't already.
2. Render dashboard -> **New + -> Web Service** -> connect the repo,
   select the branch.
3. **Root Directory**: leave blank (the repo root -- commands below
   reference `backend/` explicitly).
4. **Build Command**:
   ```
   pip install -r requirements.txt --break-system-packages
   ```
5. **Start Command**:
   ```
   PYTHONPATH=. uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT
   ```
6. **Environment Variables** -- add every row below that applies
   (leave the rest unset; unset = that capability degrades gracefully,
   nothing breaks):

#### Required for a real production deployment

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | your Neon connection string from Step 1 | Without this, accounts/projects live in ephemeral SQLite and **vanish on every redeploy**. |
| `OPENPRESENT_INPROCESS_WORKER` | `true` | Render's free/starter tier is one service -- the worker runs as a background thread inside the API process (ADR-015). Leave this as `true` unless you've provisioned a separate worker service. |

#### AI providers -- add any subset, in this priority order (ADR-030)

| Variable | Value | Priority |
|---|---|---|
| `GEMINI_API_KEY` | your key from Step 0 | 1st -- default hosted provider |
| `GROQ_API_KEY` | your key from Step 0 | 2nd -- fallback |
| `OPENROUTER_API_KEY` | your key from Step 0 | 3rd -- fallback |
| `HUGGINGFACE_API_KEY` | your key from Step 0 | 4th -- fallback |

Add as many as you want -- every one with a key present gets wired
into the cascading composite automatically; you do NOT need to set
`OPENPRESENT_AI_ADAPTER` unless you want to force exactly one provider
(see Section 5 below).

With **zero** of these set: the app still works, using the
deterministic (non-AI) topic template -- no error, just a plainer deck.

#### Image providers -- add any subset (ADR-029)

| Variable | Value |
|---|---|
| `OPENPRESENT_UNSPLASH_ACCESS_KEY` | your key from Step 0 |
| `OPENPRESENT_PEXELS_API_KEY` | your key from Step 0 |
| `OPENPRESENT_PIXABAY_API_KEY` | your key from Step 0 |

Wikimedia Commons requires nothing and is on by default. To turn it
off (not recommended -- it's the only zero-setup fallback), set
`OPENPRESENT_DISABLE_WIKIMEDIA` to `true`.

#### Research providers -- on by default (Wikipedia needs no key), add any subset to upgrade quality

| Variable | Value | Priority |
|---|---|---|
| `TAVILY_API_KEY` | your key -- tavily.com | 1st -- purpose-built for LLM grounding |
| `BRAVE_SEARCH_API_KEY` | your key -- brave.com/search/api | 2nd -- live web index |
| *(none needed)* | Wikipedia -- always on | 3rd -- real REST API, no key, guaranteed fallback |

Facts are MERGED across whichever of these are available (not just the
first one that responds) -- more configured providers means richer
grounding for the AI Strategy stage, not just redundancy. With zero
keys set, Wikipedia alone still provides real grounding, on by
default -- no flag needed to turn this on.

#### Optional extras

| Variable | Value | Effect |
|---|---|---|
| `OPENPRESENT_RESEARCH_ADAPTER` | `null` | Fully disables the Research stage (only needed if you want zero research calls at all -- e.g. for latency reasons). Leave unset to keep the default multi-provider behavior above. |
| `OPENPRESENT_ENABLE_DUCKDUCKGO_RESEARCH` | `true` | Adds DuckDuckGo HTML-scraping as an extra bonus free source alongside the default providers. Off by default -- best-effort/lower-reliability than the others, kept only as an optional add-on. |
| `SENTRY_DSN` | your DSN from Step 0 | Turns on structured error monitoring — works with Bugsink, GlitchTip, self-hosted Sentry, or Sentry SaaS interchangeably (same `sentry-sdk` protocol, no code change either way). Leave unset for no monitoring, no cost, no dependency issues. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0` for Bugsink; e.g. `0.1` for a backend that supports performance tracing | Bugsink doesn't process performance-tracing data, so set this to `0` to avoid generating and sending data it ignores. Defaults to `0.1` if `SENTRY_DSN` is set and this isn't — override it to `0` explicitly if you're on Bugsink. |
| `OPENPRESENT_GEMINI_MODEL` | e.g. `gemini-3.5-flash` | Optional override -- only set if you want a different Gemini model than the default. |
| `OPENPRESENT_GROQ_MODEL` | e.g. `llama-3.1-8b-instant` | Optional override. |
| `OPENPRESENT_OPENROUTER_MODEL` | e.g. `openrouter/free` | Optional override -- verify current free models at openrouter.ai/models before relying on this. |
| `OPENPRESENT_HUGGINGFACE_MODEL` | e.g. `meta-llama/Llama-3.1-8B-Instruct` | Optional override. |

7. Click **Create Web Service** (or **Save Changes** if editing an
   existing one) and wait for the deploy to finish.

### Verify the backend is actually live and correctly configured

Run this (replace the URL with your real Render URL):

```bash
curl https://<your-render-url>/health
```

**Read every field explicitly** -- this is the single source of truth
for what's actually turned on:

```json
{
  "status": "ok",
  "phase": 4,
  "ai_adapter": "CompositeAIAdapter",
  "ai_providers_configured": ["GeminiAdapter", "GroqAdapter"],
  "ai_available": true,
  "ai_pipeline_available": true,
  "media_adapter": "MultiProviderMediaAdapter",
  "media_providers_configured": ["unsplash", "wikimedia"],
  "media_available": true,
  "research_adapter": "CompositeResearchAdapter",
  "research_providers_configured": ["TavilyResearchAdapter", "WikipediaResearchAdapter"],
  "research_available": true,
  "sentry_active": false,
  "queue_depth": 0,
  "auth_adapter": "PostgresAuthAdapter",
  "storage_adapter": "PostgresStorageAdapter",
  "database_url_present": true
}
```

Check each field against what you expect:

- **`ai_providers_configured`** -- should list exactly the providers
  whose API keys you set, in priority order. If you set
  `GEMINI_API_KEY` but it's not in this list, the env var name has a
  typo or wasn't saved -- recheck Render's Environment tab.
- **`ai_adapter`** -- `"CompositeAIAdapter"` if 1+ AI provider is
  configured, `"NullAdapter"` if none are.
- **`media_providers_configured`** -- `"wikimedia"` should always
  appear (unless you disabled it); your keyed providers appear
  alongside it.
- **`research_providers_configured`** -- `"WikipediaResearchAdapter"`
  should always appear (unless you set
  `OPENPRESENT_RESEARCH_ADAPTER=null`); `TavilyResearchAdapter`/
  `BraveSearchResearchAdapter` appear alongside it if you set those
  keys. `research_available: true` with only Wikipedia listed is
  normal and expected -- research works with zero keys configured.
- **`database_url_present`** -- must be `true` for a real deployment.
  If `false`, go back and fix `DATABASE_URL` -- this is not optional
  for production, only for quick local testing.
- **`sentry_active`** -- `true` only if `SENTRY_DSN` is set (pointing
  at Bugsink, GlitchTip, or Sentry — all work identically) AND
  `sentry-sdk` installed correctly during build (it's in
  `requirements.txt`, so this should be automatic once `SENTRY_DSN` is
  set).

### Verify a real generation actually uses AI (not the fallback)

```bash
curl -X POST https://<your-render-url>/generate/topic \
  -H "Content-Type: application/json" \
  -d '{"topic":"A quick deployment test","slide_count":4}' \
  -o test.zip
```

Unzip `test.zip` -- you should get `presentation.pptx` and
`speaker_notes.docx`. Open the pptx:

- If the slides are **specifically about your test topic** with
  real, varied bullet points -> AI worked.
- If the slides say generic things like "Background", "Key Points",
  "Why It Matters" -> it silently fell back to the deterministic
  template. Check Render's **Logs** tab for the actual error (most
  common cause: an invalid, expired, or not-yet-activated API key).

Open `speaker_notes.docx` and confirm it lists real notes per slide,
separate from the pptx's own (also real) speaker notes -- the fact
that both exist and both look correct confirms the ADR-029 notes-bug
fix is deployed.

---

## 3. Vercel (frontend)

### If you already have the Vercel project set up:

Nothing needs to change -- redeploy (push to your watched branch, or
**Deployments -> Redeploy**) to pick up the updated topic-generation
UI and the zip-download filename fix.

### If setting up fresh:

1. Vercel dashboard -> **Add New -> Project** -> import your repo.
2. **Root Directory**: `frontend`
3. **Framework Preset**: Next.js (auto-detected).
4. **Environment Variables**:

   | Variable | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE` | `https://<your-render-url>` (no trailing slash) |

5. Click **Deploy**.

### Verify the frontend is live

Open your Vercel URL. Confirm:

- The homepage loads with **"Generate from a topic"** as the selected
  tab.
- Generate a real deck through the UI. The download should be a
  `presentation.zip` file (not `.pptx` directly) -- this is expected;
  unzip it to get both files.
- The "Downloaded" confirmation text should mention "(.pptx + speaker
  notes .docx, zipped)" -- if it just says "Downloaded" with no
  mention of the zip, the frontend build is stale; redeploy.

---

## 4. Explicit end-to-end checklist

Go through every line. Don't skip any -- each checks a different part
of this build.

- [ ] `curl https://<render-url>/health` returns `"status": "ok"`
- [ ] `database_url_present` is `true`
- [ ] `ai_providers_configured` lists every AI provider whose key you
      set -- none missing, none unexpected
- [ ] `media_providers_configured` includes `"wikimedia"` plus any
      keyed providers you added
- [ ] `research_providers_configured` includes
      `"WikipediaResearchAdapter"` plus any keyed providers you added
- [ ] `sentry_active` matches whether you set `SENTRY_DSN`
- [ ] A real `POST /generate/topic` call produces a genuinely
      on-topic deck (not the generic fallback template)
- [ ] The response unzips into both `presentation.pptx` AND
      `speaker_notes.docx`
- [ ] Opening the pptx: speaker notes are in PowerPoint's actual Notes
      pane (View -> Notes in PowerPoint/Google Slides), not visible
      as bullets on the slide itself
- [ ] `POST /generate` (document upload) still works -- this path is
      unchanged logic-wise but shares the same bundling change
- [ ] Frontend homepage loads, topic form is the default tab
- [ ] A real generation through the frontend UI downloads a working
      `.zip`
- [ ] Register -> generate -> check `GET /projects` shows it saved,
      and it's **still there after a Render redeploy** (confirms
      Neon, not ephemeral SQLite, is actually in use)
- [ ] Document upload (second tab) still works -- quick smoke test

---

## 5. Forcing a single AI provider (testing/debugging only)

By default, every configured provider is combined into a fallback
ladder. To isolate exactly one provider (e.g. to debug whether Gemini
specifically is misbehaving), set:

```
OPENPRESENT_AI_ADAPTER=gemini
```

Valid values: `local_model`, `gemini`, `groq`, `openrouter`,
`huggingface`, `null`. This **bypasses the fallback composite
entirely** -- only use it temporarily for debugging, then unset it to
restore the full ladder for production.

---

## 6. Rollback / turning capabilities off without a redeploy

Every capability in this build is an environment variable, not a code
path you need to revert:

| To turn off... | Do this |
|---|---|
| All AI (revert to deterministic decks) | Remove all `*_API_KEY` AI vars, or set `OPENPRESENT_AI_ADAPTER=null` |
| One misbehaving AI provider | Remove just that provider's `*_API_KEY` -- the composite automatically drops it from the ladder |
| All non-Wikimedia images | Remove `OPENPRESENT_UNSPLASH_ACCESS_KEY`, `OPENPRESENT_PEXELS_API_KEY`, `OPENPRESENT_PIXABAY_API_KEY` |
| All images including Wikimedia | Also set `OPENPRESENT_DISABLE_WIKIMEDIA=true` |
| The AI quality-review revision pass | Not independently toggleable -- it's now default behavior (ADR-030); it only fires when the $0 deterministic validator finds real issues, so it's rarely a cost concern |
| Research stage entirely | Set `OPENPRESENT_RESEARCH_ADAPTER=null` |
| Just the paid research providers (keep Wikipedia) | Remove `TAVILY_API_KEY` and `BRAVE_SEARCH_API_KEY` |
| Sentry | Remove `SENTRY_DSN` |
| Speaker-notes DOCX bundling | Not an env var -- pass `"bundle_speaker_notes": false` in the request body per-call |

In every case: redeploy after changing env vars on Render, nothing
goes down, generation keeps working throughout -- this is the whole
point of every fallback layer being real and tested (154 automated
tests cover exactly these degradation paths).

---

## 7. Costs to expect

- **Gemini / Groq / OpenRouter / HuggingFace free tiers**: each has
  its own rate limits that change over time -- check current limits
  at each provider's site before assuming capacity. If
  `/generate/topic` starts falling back to the deterministic template
  under real traffic, check Render's logs for `429`-style errors and
  consider adding more providers to the ladder or upgrading one to a
  paid tier.
- **Unsplash / Pexels / Pixabay**: 50/200/5000 requests-per-hour
  respectively (self-tracked in-process -- see ADR-029); Wikimedia has
  no documented hard limit at this usage level.
- **Sentry**: free tier covers a meaningful volume for an MVP; watch
  your event quota if traffic grows.
- **Render / Vercel / Neon**: unchanged by this build -- no new
  infrastructure, only new outbound API calls from the existing
  backend service.
- **Per-generation AI cost**: up to 5-6 model calls now (Strategy,
  Outline, Content, Layout Planning, optional Research, optional
  Review) versus 1-2 in the previous build -- a deliberate, explicit
  tradeoff (see ADR-030) for pipeline quality. Monitor provider
  dashboards if you're on a metered tier anywhere in the ladder.
