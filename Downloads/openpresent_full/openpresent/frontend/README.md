# OpenPresent Frontend

Next.js 14 (App Router), TypeScript. Built and verified: `npm run build`
compiles clean (6 routes, TS type-checking passes), `npm run dev` serves
working pages.

## Design identity

"The desk lamp is on, your notes are covered in highlighter, the
deadline is tomorrow." Deep navy + warm paper + one amber highlighter
accent — deliberately not the generic cream/terracotta AI-tool look.
Signature element: a rough marker-stroke underline (`.highlight` in
`globals.css`) used sparingly on key phrases. Index-card motif on the
dashboard evokes a physical stack of study notes.

## Structure

- `app/page.tsx` — landing page; the hero IS the generate flow, not
  marketing copy about it (upload -> real download, no account needed)
- `app/login`, `app/register` — auth
- `app/dashboard` — saved projects (index-card grid)
- `app/projects/[id]` — project detail + export
- `lib/api-client.ts` — the ONLY place that calls the backend, per
  `docs/OPENPRESENT_CODEBASE.md` Section 2

## Run it

```bash
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev
```

Requires the backend running (see `../README.md`).

## Known sandbox-only quirk

The production build shows a font-optimization warning because this
dev sandbox can't reach fonts.googleapis.com (not in the network
allowlist). It's non-fatal — the build still succeeds — and won't
occur in a normal deployment with real internet access.
