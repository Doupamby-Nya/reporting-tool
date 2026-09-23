# Regulatory reporting — web client

React 19 + TypeScript + Vite + Tailwind, with server-side rendering through
Express, matching the platform's reference frontend.

## Setup

```
npm install
npm run dev        # SSR dev server on :3000
npm run build      # client + SSR bundles
npm run lint
```

`VITE_BACKEND_URL` in `.env` points at the API and already carries the
`/api/v1` prefix, so every path in `src/api/reportingApi.ts` is relative to
it.

## Layout

```
src/
  api/          api.tsx (axios instance) and reportingApi.ts (one call per endpoint)
  components/   ValidationReport, FileDownload — shared by every regime
  layouts/      MainLayout: the brand bar and the module navigation
  pages/        one page per regime, plus the overview and the audit trail
  routes/       AppRouter (browser) and SSRRouter (server), same tree
  types/        the shapes the API returns
```

`reportingApi.ts` unwraps the API's `{success, result, message}` envelope
into a value or a thrown Error, so a page uses one `try/catch` rather than
branching on `success` at every call site.
