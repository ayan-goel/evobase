# Agent Optimization Strategy — React (Vite / CRA)

This covers React Single-Page Applications built with Vite (the modern default) or Create React App. These are fully client-rendered — unlike Next.js, everything is a "client component" by definition. Optimization focuses on render performance, bundle size, and state management efficiency.

---

## Detection

| Signal | Confidence |
|---|---|
| `react` in deps + `vite` in devDeps | 0.95 → `react-vite` |
| `react-scripts` in deps | 0.9 → `react-cra` |
| `react` in deps, no `next` / `gatsby` / `remix` / `vite` | 0.7 → `react` |
| `vite.config.ts` exists | +0.1 boost |

---

## Category 1 — Unnecessary Re-renders

### Why it matters

React re-renders a component every time its parent re-renders, unless it is wrapped in `React.memo`. In a list of 100 items, a single state update at the top can trigger 100 unnecessary renders — visible as dropped frames and janky UIs.

### What to look for

1. **List item components not wrapped in `React.memo`**:
   ```tsx
   // BAD: re-renders on every parent state change
   function TodoItem({ todo }: { todo: Todo }) {
     return <li>{todo.title}</li>;
   }

   // GOOD
   const TodoItem = React.memo(function TodoItem({ todo }: { todo: Todo }) {
     return <li>{todo.title}</li>;
   });
   ```

2. **Inline object, array, or function props** passed to any component — these create a new reference on every render, causing `React.memo` to always re-render:
   ```tsx
   // BAD: `{ color: "red" }` is a new object each render
   <Chart config={{ color: "red" }} onHover={() => setHighlight(true)} />

   // GOOD
   const chartConfig = useMemo(() => ({ color: "red" }), []);
   const handleHover = useCallback(() => setHighlight(true), []);
   <Chart config={chartConfig} onHover={handleHover} />
   ```

3. **Context consumers that re-render when unrelated context values change** — look for large context objects where only one field is consumed.

4. **Components that use `useSelector` (Redux/Zustand) without proper selector memoization**, causing re-renders when unrelated store slices change.

### Agent rules

- Add `React.memo` to leaf components used in lists or grids.
- Wrap inline object/array props in `useMemo` at the call site.
- Wrap inline function props in `useCallback`.

---

## Category 2 — Expensive Computations in Render

### Why it matters

Calculations done directly in the render function run on every render — even if the inputs haven't changed. `useMemo` memoizes the result so it only re-computes when dependencies change.

### What to look for

1. **Filtering/sorting/grouping arrays directly in render**:
   ```tsx
   // BAD: re-computes sorted list on every render
   function ProductList({ products, search }: Props) {
     const filtered = products
       .filter(p => p.name.includes(search))
       .sort((a, b) => a.price - b.price);
     return <ul>{filtered.map(...)}</ul>;
   }

   // GOOD
   const filtered = useMemo(
     () => products.filter(p => p.name.includes(search)).sort((a, b) => a.price - b.price),
     [products, search]
   );
   ```

2. **Building derived data structures** (maps, sets, grouped objects) inline.

3. **Regex construction inside render** — `new RegExp(pattern)` should be hoisted to module scope or wrapped in `useMemo`.

### Agent rules

- Wrap computations over arrays with more than ~10 items in `useMemo`.
- Move regex construction outside render.

---

## Category 3 — Context API Misuse

### Why it matters

Every consumer of a Context will re-render when the context value changes — even if the value they need didn't change. Large, monolithic contexts that update frequently are a significant performance sink.

### What to look for

1. **One large context object** updated frequently — should be split into stable and dynamic parts:
   ```tsx
   // BAD: updating `cart` re-renders all `user` consumers
   const AppContext = createContext({ user: ..., cart: ..., theme: ... });

   // GOOD: separate contexts
   const UserContext = createContext(user);
   const CartContext = createContext(cart);
   ```

2. **Context `value` created inline** in the Provider — creates a new object every render:
   ```tsx
   // BAD
   <MyContext.Provider value={{ user, logout }}>

   // GOOD
   const contextValue = useMemo(() => ({ user, logout }), [user, logout]);
   <MyContext.Provider value={contextValue}>
   ```

3. **Using Context for high-frequency data** (e.g. mouse position, scroll position) — this should be handled with refs or a state management library that supports granular subscriptions.

### Agent rules

- Memoize the Provider's `value` prop with `useMemo`.
- Flag large context objects that mix rarely-updated (user) and frequently-updated (notifications) data.

---

## Category 4 — `useEffect` Anti-patterns

### Why it matters

`useEffect` with incorrect dependencies causes either stale closures (missing deps) or infinite loops (over-specified deps). Both lead to bugs and degraded performance.

### What to look for

1. **Effects with empty `[]` dependencies that reference props or state** — these capture initial values and go stale:
   ```tsx
   // BUG: `count` is stale after first render
   useEffect(() => {
     const interval = setInterval(() => console.log(count), 1000);
     return () => clearInterval(interval);
   }, []); // should include `count`
   ```

2. **Effects that just fetch data on mount** and could be replaced with a proper data-fetching library (`react-query`, `swr`) or a loader pattern:
   ```tsx
   // Fragile: no loading state, no error handling, no cache
   useEffect(() => {
     fetch("/api/data").then(r => r.json()).then(setData);
   }, []);
   ```

3. **Effects that derive state from props** — these should use direct computation during render, not an effect:
   ```tsx
   // BAD: effect sets derived state (causes extra render)
   useEffect(() => {
     setFullName(`${firstName} ${lastName}`);
   }, [firstName, lastName]);

   // GOOD: derive in render
   const fullName = `${firstName} ${lastName}`;
   ```

4. **Missing cleanup** for subscriptions, event listeners, or timers — causes memory leaks.

### Agent rules

- Flag `useEffect` calls with empty deps that reference reactive values.
- Replace simple data-fetch effects with `use()` (React 19) or note the opportunity for `react-query`/`swr`.
- Flag effects that set state based solely on props as derivable in render.
- Flag effects without cleanup that create subscriptions or timers.

---

## Category 5 — Bundle Size

### Why it matters

Larger bundles = longer parse/execute time = worse FCP and TTI, especially on mobile.

### What to look for

1. **Barrel file imports** that prevent tree-shaking:
   ```tsx
   // BAD: imports entire lodash
   import { debounce } from "lodash";

   // GOOD: imports only debounce
   import debounce from "lodash/debounce";
   ```

2. **Moment.js** — replace with `date-fns` or `dayjs`. Moment bundles every locale.

3. **Full icon library imports** (e.g. `import * as Icons from "@heroicons/react/24/solid"`):
   ```tsx
   // BAD
   import * as Icons from "@heroicons/react/24/solid";
   const icon = Icons[name];

   // GOOD: import by name
   import { HomeIcon } from "@heroicons/react/24/solid";
   ```

4. **Heavy components not code-split** — modals, rich text editors, charts that only appear after user interaction:
   ```tsx
   const Editor = lazy(() => import("./Editor"));
   ```

5. **Dependencies included in the dev bundle at runtime** — check `vite.config.ts` for missing `optimizeDeps` or incorrect `build.rollupOptions`.

### Agent rules

- Replace `lodash` whole-package imports with specific function imports.
- Flag `moment` and suggest `date-fns`.
- Wrap infrequently-rendered heavy components in `React.lazy` + `Suspense`.

---

## Category 6 — State Management Efficiency

### Why it matters

Poorly structured global state causes unnecessary renders and makes debugging harder.

### What to look for

1. **State stored high in the tree when it's only used by one sub-tree** — should be localized.

2. **Zustand stores with no selector usage** — consumers subscribe to the entire store:
   ```ts
   // BAD: re-renders on any store change
   const { user, cart, theme } = useStore();

   // GOOD: granular selectors
   const user = useStore(s => s.user);
   ```

3. **Redux: missing `createSelector` for derived data** — recomputes on every dispatch.

4. **State that is really a URL param** — modal open/closed state, filter values, tab selection — should live in the URL (enables deep linking, back button support).

### Agent rules

- Flag store subscriptions that destructure multiple unrelated slices.
- Flag derived state (filtered lists, computed totals) not protected by `createSelector` or equivalent.

---

## System Prompt

```
Focus areas for React (Vite / SPA):
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
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Re-render reduction | Component render count | React DevTools Profiler |
| Bundle size | Bundle size (KB) | `vite-bundle-visualizer` / `rollup-plugin-visualizer` |
| Context split | Context update propagation | React DevTools |
| useMemo | Computation time (ms) | React DevTools Profiler |
| Code splitting | Chunk load time | Chrome DevTools Network |
