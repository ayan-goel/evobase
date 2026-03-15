"""Svelte and SvelteKit optimization focus areas."""

FOCUS = """
Focus areas for Svelte / SvelteKit:

-- Existing patterns --
- Reactive declarations ($:): async side effects (fetch, API calls) inside $: statements
  that should be explicit function calls; circular reactive dependencies.
- Store subscriptions: manual subscribe() calls without onDestroy cleanup (memory leaks);
  components subscribing to a large store to read one field (suggest derived stores).
- SvelteKit load functions: database/ORM calls in universal +page.ts load functions
  instead of server-only +page.server.ts; sequential awaits for independent resources
  (use Promise.all).
- {#each} keys: missing key expression in {#each} blocks over objects with unique IDs.
- Lazy loading: heavy component imports inside {#if} blocks that could use dynamic
  import() to defer loading.
- CSS transitions: transitions on layout properties (width, height, top, left) instead
  of transform/opacity (composite-only properties avoid layout thrashing).

-- Rule catalog (apply low-risk first) --

Rule SV-KEY-001 — Unkeyed {#each} over mutable arrays
  Anti-pattern : `{#each items as item}` without a key expression when items
                 have stable unique identifiers
  Detection    : regex — `{#each <items> as <item>}` without `(<key>)` key syntax
  Patch (medium): Add stable key: `{#each items as item (item.id)}`
  Validate     : UI reorder and mutation tests; check no focus/animation regressions
  Rollback if  : UI state bugs (form fields, animations reset incorrectly)
  Do NOT apply : items have no stable identity (purely positional display)

Rule SV-LAZY-002 — Heavy component always eagerly imported
  Anti-pattern : Heavy component imported at the top of a .svelte file but only
                 conditionally rendered with `{#if ...}`
  Detection    : AST — static import of a component whose file size > 50 kB;
                 that component only appears inside `{#if}` in the template
  Patch (medium): Replace static import with dynamic: `const Heavy = import('./Heavy.svelte')`
                 and use `{#await Heavy}` or an `{#if loaded}` guard with
                 `import()` triggered on demand
  Validate     : Lighthouse CI initial JS size; interaction test
  Rollback if  : component needed at first render; loading flash breaks UX
  Do NOT apply : component is required at first paint

Rule SK-LOAD-001 — Secrets / DB access in universal +page.ts
  Anti-pattern : `+page.ts` (universal load, runs on both server and browser)
                 importing DB clients, private env vars, or server-only modules
  Detection    : file pattern — `+page.ts` (not `+page.server.ts`) containing
                 imports of `$env/static/private`, `$lib/server/*`, or ORM clients
  Patch (medium): Move the load function to `+page.server.ts`; expose only
                 serializable data in the returned object
  Validate     : SSR build (`vite build`) + e2e
  Rollback if  : SSR hydration mismatch; browser needs data-only variant
  Do NOT apply : data genuinely required in both server and browser contexts

Rule SK-WATERFALL-002 — Sequential awaits for independent resources in load
  Anti-pattern : `const a = await fetchA(); const b = await fetchB()` in a
                 `load` function where fetchA and fetchB are independent
  Detection    : AST — consecutive `await` expressions in a load function whose
                 awaitees have no data dependency on each other
  Patch (medium): Parallelize with `const [a, b] = await Promise.all([fetchA(), fetchB()])`
                 or stream non-essential data via nested promise return
  Validate     : WPT/Lighthouse TTFB comparison; e2e correctness
  Rollback if  : UX regressions if partial data looks broken; error handling
                 complexity increases
  Do NOT apply : fetches are genuinely sequential (B depends on A's result)

Rule SK-PRERENDER-003 — Static routes not prerendered
  Anti-pattern : Routes that serve fully static content (blog posts, docs, marketing
                 pages) without `export const prerender = true`
  Detection    : file — `+page.svelte` / `+page.server.ts` with no dynamic
                 params, no session/auth dependency, and no `prerender` export
  Patch (medium): Add `export const prerender = true` to the load file
  Validate     : `vite build` succeeds; smoke test the prerendered HTML
  Rollback if  : stale content; build fails due to dynamic data dependency
  Do NOT apply : route has dynamic params, auth gates, or real-time data

Rule SK-ENV-004 — Browser-only imports in server-evaluated modules
  Anti-pattern : `+page.ts` or `+layout.ts` importing browser-only libs
                 (e.g. `localStorage`, browser-only SDKs)
  Detection    : AST — import of known browser-only module in a non-.svelte file
                 under src/routes/
  Patch (low/medium): Move import to the `.svelte` component body or guard with
                 `if (browser) { const mod = await import(...) }`
  Validate     : SSR build (no window/document reference errors)
  Rollback if  : functionality missing at runtime; SSR crashes
  Do NOT apply : module is explicitly designed for SSR usage
"""
