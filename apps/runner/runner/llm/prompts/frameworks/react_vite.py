"""React (Vite / SPA) optimization focus areas."""

FOCUS = """
Focus areas for React (Vite / SPA):

-- Existing patterns --
- Unnecessary re-renders: list item components not wrapped in React.memo; inline object/
  array/function props that create new references on every render; context consumers that
  receive the full context object when only one field is needed.
- Expensive in-render computations: array filtering/sorting/grouping done inline in the
  render body that should be wrapped in useMemo; regex construction inside render.
- Context API misuse: Provider value created inline as an object literal (new reference
  each render); large monolithic contexts that mix high-frequency and low-frequency data.
- useEffect anti-patterns: empty dependency arrays that reference reactive values (stale
  closures); effects that derive state from props (should be derived in render); effects
  without cleanup for subscriptions/timers.
- Bundle size: full lodash imports instead of per-function imports; Moment.js (replace
  with date-fns); heavy components not wrapped in React.lazy + Suspense; barrel file
  index.ts imports preventing tree-shaking.
- State management: Zustand/Redux store consumers that subscribe to the entire store
  without granular selectors; derived data not protected by memoized selectors.

-- Rule catalog (apply low-risk first) --

Rule RV-MEMO-001 — Expensive derived data recomputed on every render
  Anti-pattern : `.filter()`, `.sort()`, `.reduce()`, `.map()` assigned inline in
                 a function component body and used in JSX
  Detection    : TS/JS AST — array method chain in component body assigned to a
                 const that is referenced in JSX; not already inside useMemo
  Patch (low/medium): Wrap with `useMemo(() => computation, [deps])`
  Validate     : React Profiler render counts + unit tests
  Rollback if  : no measurable improvement; stale-closure symptoms
  Do NOT apply : computation depends on unstable refs or non-reactive values

Rule RV-CB-002 — Inline callbacks causing avoidable child rerenders
  Anti-pattern : JSX prop value is an ArrowFunctionExpression; child component
                 is wrapped in React.memo
  Detection    : JSX AST — `prop={() => ...}` on a component whose definition
                 has `React.memo(...)` or `memo(...)`
  Patch (medium): Hoist and wrap with `useCallback(fn, [deps])`
  Validate     : React Profiler + e2e
  Rollback if  : stale-closure bugs; callback captures mutable state
  Do NOT apply : callback captures complex mutable state with non-obvious deps

Rule RV-EFFECT-003 — Derived state computed in useEffect
  Anti-pattern : `useEffect(() => setState(f(props/state)), [deps])` where the
                 new state is a pure transformation of existing state/props
  Detection    : AST — `useEffect` body contains exactly one `setState(f(...))` call
                 where f's argument is a prop or state value
  Patch (medium): Remove the effect; compute derived value directly in render body
  Validate     : Unit tests + e2e behaviour comparison
  Rollback if  : computed value is needed at the wrong point in the lifecycle
  Do NOT apply : effect synchronizes an external system (DOM, subscription, timer)

Rule RV-KEYS-004 — Array index used as React key
  Anti-pattern : `.map((item, index) => <Component key={index} ...>)`
  Detection    : JSX AST — `key={index}` or `key={i}` in a `.map()` callback where
                 index is the second parameter
  Patch (medium): Use a stable unique ID: `key={item.id}` or `key={item.slug}`
  Validate     : List reorder interaction tests
  Rollback if  : UI state bugs (input focus, animation)
  Do NOT apply : items have no stable identity (purely positional display)

Rule RV-SPLIT-005 — Single huge entry bundle
  Anti-pattern : bundle chunk exceeds threshold; heavy deps imported statically
                 in the app entry or a route component
  Detection    : build artifact — Rollup/Vite stats chunk > 250 kB gzipped for a
                 single chunk; or static import of known-heavy pkg in entry
  Patch (medium): Use dynamic `import()` for route-level or conditionally-used features;
                  wrap with `React.lazy(() => import('./Feature'))` + `<Suspense>`
  Validate     : Bundle diff + Lighthouse CI initial JS
  Rollback if  : feature loads too late; first-paint interaction broken
  Do NOT apply : feature is required at first paint or above the fold

Rule RV-VITE-006 — Slow dev start / build due to config anti-patterns
  Anti-pattern : large plugin chains in vite.config; barrel file (index.ts)
                 re-exports causing resolve churn on every HMR
  Detection    : file — vite.config.ts plugin array length > 8; or index.ts files
                 with 20+ re-exports in src/
  Patch (high) : Advisory — restructure imports, reduce barrel depth, follow
                 Vite performance guide (https://vitejs.dev/guide/performance)
  Validate     : CI build wall-clock time comparison
  Rollback if  : build regressions
  Do NOT apply : repo-specific framework constraints require current structure
"""
