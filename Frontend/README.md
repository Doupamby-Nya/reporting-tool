# Regulatory reporting — web client

React 19 + TypeScript + Vite + Tailwind, with server-side rendering through
Express, matching the platform's reference frontend.

## Setup

Requires Node.js 20 or later. Create `Frontend/.env` first:

```
VITE_BACKEND_URL=http://localhost:8001/api/v1
```

It must carry the `/api/v1` prefix: every path in `src/api/reportingApi.ts`
is relative to it. Without it the client falls back to
`http://localhost:8000` and no call reaches the API.

```
npm install
npm run dev        # SSR dev server on http://localhost:4000 (server.js; PORT to change it)
npm run build      # client + SSR bundles into dist/
npm run lint
npx tsc --noEmit   # type-check
```

The production server (`server-prod.js`, used by the `Dockerfile`) listens
on `PORT`, 3000 by default. The API's `CORS_ORIGINS` must list whichever
origin the client is served from.

Optional, in the same `.env`:

```
VITE_DEMO_VIDEO_URL=https://www.youtube-nocookie.com/embed/<id>   # the home page's demo video
VITE_CONTACT_EMAIL=someone@forvismazars.com                         # the "Request access" button
```

`SSR_BACKEND_URL` (a process variable of the Node server) overrides the API
address used during server rendering, for a deployment where the server
reaches the API differently from the browser.

## Signed-in rendering

The session is an `httpOnly` cookie set by the API. When rendering a page,
the Node server forwards the browser's cookie to `GET /auth/me` and renders
for that user; the result is handed to the client store as
`window.__PRELOADED_STATE__`, so the tabs are right from the first paint and
hydration starts from the same state. In production, serve the client and
the API under one domain (a reverse proxy on `/api`) so the cookie reaches
both.

## Layout

```
src/
  api/          api.tsx (axios instance) and reportingApi.ts (one call per endpoint)
  config/       navigation.ts: the modules and their production chains (the router is generated from it);
                catalogue.ts: how each module and step is presented (home page, guide, logos)
  components/   shared building blocks: IngestionPanel, ValidationReport, ModuleGate, ModuleLogo, ...
  layouts/      MainLayout (header, account, the tabs the user may see) and ChainLayout (a module's step panel)
  hooks/        useCurrentUser (the account and its modules), useChain, useDrafts
  store/        Redux slices: the signed-in user, each module's chain state
  pages/
    Home.tsx                   the public home page
    Login.tsx                  signing in
    Dashboard.tsx              the user's filings, in their modules
    Guide.tsx                  capabilities (visitors) or step by step (subscribers)
    <reporting>/               Home.tsx (landing page of /<reporting>) and that reporting's own steps
    shared/                    the steps every reporting shares: ingestion, rules, generation,
                               preview, controls & audit, regulatory reference
  routes/       AppRouter (browser) and SSRRouter (server), same tree
  types/        the shapes the API returns
```

`reportingApi.ts` unwraps the API's `{success, result, message}` envelope
into a value or a thrown Error, so a page uses one `try/catch` rather than
branching on `success` at every call site.

The client has no tests of its own yet; `npx tsc --noEmit` and
`npm run build` are the only automated checks.
