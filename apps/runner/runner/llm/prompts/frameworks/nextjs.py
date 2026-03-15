"""Next.js App Router optimization focus areas."""

FOCUS = """
Focus areas for Next.js App Router:

-- Existing patterns --
- Incorrect `"use client"` boundaries: components that can be Server Components
  but are unnecessarily marked as client components, bloating the JS bundle.
- Missing `React.memo`, `useMemo`, or `useCallback` in client components that
  re-render frequently with the same props.
- Data fetching patterns: `fetch()` calls without caching options, missing
  `revalidate`, or redundant fetches that could be consolidated.
- Image optimisation: `<img>` tags that should use `<Image>` from next/image.
- Bundle splitting: large `import` statements in server components that could
  use dynamic `import()` with `{ ssr: false }`.
- Streaming opportunities: pages that block on slow data that could use
  `<Suspense>` with streaming.
- Route handler inefficiencies: middleware applied to routes that don't need it.

-- Rule catalog (apply low-risk first) --

Rule NEXT-IMG-001 — Raw <img> instead of next/image
  Anti-pattern : `<img src=...>` in app code (not dangerouslySetInnerHTML)
  Detection    : JSX AST — `<img` element in .tsx/.jsx under app/ or pages/
  Patch (medium): Convert to `<Image>` from next/image; add explicit width/height/priority
  Validate     : Screenshot diff + Lighthouse CI (LCP, CLS)
  Rollback if  : Layout distortion or LCP regression
  Do NOT apply : image dimensions unknown or layout relies on intrinsic sizing

Rule NEXT-LCP-002 — Lazy-loading the LCP/hero image
  Anti-pattern : `loading="lazy"` on the above-the-fold hero image
  Detection    : regex `loading=["']lazy["']` near hero/banner JSX; Lighthouse
                 LCP element points to a lazy image
  Patch (low)  : Remove `loading="lazy"` from the LCP image; add `priority` prop
                 on `<Image>` where feasible
  Validate     : Lighthouse CI median LCP (5 runs)
  Rollback if  : LCP regression
  Do NOT apply : cannot reliably identify LCP element statically

Rule NEXT-DYN-003 — Heavy client-only libs in initial bundle
  Anti-pattern : top-level static import of monaco-editor, chart.js, three,
                 @mui/* etc. in a client component used on the first paint
  Detection    : AST — import of known-heavy package in a file with "use client"
                 that is imported from a layout/page without `dynamic()`
  Patch (medium): Replace with `next/dynamic(() => import('./Heavy'), { ssr: false })`
  Validate     : Bundle diff + route smoke test + Lighthouse CI
  Rollback if  : above-the-fold interaction delayed; hydration mismatch
  Do NOT apply : component is required at first paint

Rule NEXT-CACHE-004 — Missing revalidation on stable server data
  Anti-pattern : App Router server `fetch(url)` without `cache` or `next.revalidate`
                 in server components or route handlers
  Detection    : AST — `fetch(` call in a file without "use client" that lacks
                 `{ cache: ... }` or `{ next: { revalidate: ... } }` in options
  Patch (medium): Add `{ next: { revalidate: N } }` or `cache: 'force-cache'`
  Validate     : Data freshness tests + e2e smoke
  Rollback if  : stale data served to users
  Do NOT apply : auth/personalized data; unclear invalidation boundaries

Rule NEXT-HEADERS-005 — Missing security headers / CSP scaffolding
  Anti-pattern : `next.config.*` has no `headers()` function; no CSP present
  Detection    : file — next.config.js/ts lacks `async headers()` export
  Patch (high) : Add report-only CSP scaffold via `headers()` in next.config
  Validate     : Security header scan + e2e
  Rollback if  : breaks inline scripts or third-party tags
  Do NOT apply : unknown inline script usage; third-party tags not audited

Rule NEXT-RSC-006 — Client-side fetch of stable server data
  Anti-pattern : `"use client"` component with `useEffect(() => fetch(url), [])`
                 for data that is not user-specific and doesn't need browser context
  Detection    : AST — `useEffect` containing `fetch(` with empty deps in a
                 "use client" file imported from a route
  Patch (high) : Advisory only — suggest migration to a Server Component fetch;
                 requires manual review of data dependencies
  Validate     : Full e2e + hydration mismatch checks
  Rollback if  : behaviour mismatch; SSR/client data divergence
  Do NOT apply : data depends on browser-only context (localStorage, window, etc.)
"""
