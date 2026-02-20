# Agent Optimization Strategy — Vue.js / Nuxt

Covers Vue 3 (Composition API) and Nuxt 3. Vue's reactivity system is different from React's — it uses Proxy-based observation rather than diffing a virtual DOM tree. Most Vue performance issues come from abusing the reactivity system, incorrect use of `v-if` vs `v-show`, and re-rendering caused by wrong use of `computed` vs `methods`.

---

## Detection

| Signal | Confidence |
|---|---|
| `vue` in deps | 0.85 → `vue` |
| `nuxt` in deps | 0.95 → `nuxt` |
| `nuxt.config.ts` exists | 0.9 |
| `<template>` + `<script setup>` patterns | confirms Vue 3 |

---

## Category 1 — Reactivity System Misuse

### Why it matters

Vue's reactivity system automatically tracks dependencies. Using the wrong API makes the system track more than necessary, triggering wasted re-renders or missing updates.

### What to look for

1. **`reactive()` wrapping primitive values** — primitives lose reactivity when destructured from a `reactive` object. Use `ref()` instead:
   ```ts
   // BAD: counter loses reactivity when destructured
   const state = reactive({ counter: 0 });
   const { counter } = state; // this is now a plain number

   // GOOD
   const counter = ref(0);
   ```

2. **Replacing the entire reactive object** instead of mutating it — Vue loses tracking:
   ```ts
   // BAD: Vue loses the reference
   let state = reactive({ items: [] });
   state = reactive({ items: newItems }); // watchers on `state` are now stale

   // GOOD
   state.items = newItems;
   ```

3. **Using `computed` with side effects** — `computed` should be pure. Side effects belong in `watch` or `watchEffect`.

4. **`watchEffect` with heavy computations** that should be `computed` (because `computed` caches):
   ```ts
   // BAD: runs every time anything in the effect reads, no caching
   watchEffect(() => {
     expensiveResult.value = items.value.filter(...).sort(...);
   });

   // GOOD: only re-runs when `items` changes, result is cached
   const expensiveResult = computed(() => items.value.filter(...).sort(...));
   ```

### Agent rules

- Flag `reactive()` wrapping a single primitive — suggest `ref()`.
- Flag `watchEffect` that assigns to a `ref` based on other reactive values — suggest `computed`.

---

## Category 2 — `v-if` vs `v-show`

### Why it matters

- `v-if`: destroys and recreates the DOM node. Expensive for complex components, cheap for rarely-shown content.
- `v-show`: toggles CSS `display`. Cheap to toggle, but always renders the component (including its initial mount).

Using the wrong one causes either sluggish toggling or wasted initial render work.

### What to look for

1. **`v-if` on elements that toggle frequently** (tab panels, dropdown content that opens/closes often):
   ```html
   <!-- BAD: destroys/recreates complex form on every toggle -->
   <ComplexForm v-if="isVisible" />

   <!-- GOOD: keeps form alive, just hides it -->
   <ComplexForm v-show="isVisible" />
   ```

2. **`v-show` on elements that are rarely shown** or that contain sensitive content (admin panels, error states) — waste memory and DOM nodes:
   ```html
   <!-- BAD: admin panel always in DOM -->
   <AdminPanel v-show="isAdmin" />

   <!-- GOOD: not in DOM for regular users -->
   <AdminPanel v-if="isAdmin" />
   ```

### Agent rules

- If a `v-if` element is toggled by a button/click with no data loading involved → suggest `v-show`.
- If a `v-show` element is on a condition unlikely to be true (permission check, error state) → suggest `v-if`.

---

## Category 3 — List Rendering with `v-for`

### Why it matters

Vue needs a `:key` to efficiently diff lists. Without a stable key, Vue may re-render the wrong elements or re-use DOM nodes with stale state.

### What to look for

1. **`v-for` with `:key="index"`** — using the array index as the key means Vue can't tell when items are reordered or inserted in the middle:
   ```html
   <!-- BAD: index keys cause bugs when items are reordered -->
   <li v-for="(item, index) in items" :key="index">

   <!-- GOOD: stable unique id -->
   <li v-for="item in items" :key="item.id">
   ```

2. **`v-for` + `v-if` on the same element** — Vue evaluates `v-if` first in Vue 3, but this is a readability/performance antipattern. Filter the array in `computed` instead:
   ```html
   <!-- BAD: iterates all items, then filters in template -->
   <li v-for="item in items" v-if="item.visible" :key="item.id">

   <!-- GOOD -->
   <li v-for="item in visibleItems" :key="item.id">
   ```
   ```ts
   const visibleItems = computed(() => items.value.filter(i => i.visible));
   ```

3. **Large lists without virtualization** — lists of hundreds of items should use `vue-virtual-scroller` or `tanstack-virtual`.

### Agent rules

- Replace `:key="index"` with `:key="item.id"` (or another stable identifier from the item).
- Extract `v-for` + `v-if` combinations into a `computed` property.

---

## Category 4 — `computed` vs `methods`

### Why it matters

`computed` properties are cached and only re-evaluate when their dependencies change. `methods` re-execute on every render. Using a method where a computed property would work wastes CPU.

### What to look for

1. **Methods called in templates that derive data from reactive state**:
   ```html
   <!-- BAD: getFullName() runs on every re-render -->
   <p>{{ getFullName() }}</p>

   <!-- GOOD: fullName only re-runs when firstName or lastName changes -->
   <p>{{ fullName }}</p>
   ```
   ```ts
   // BAD
   methods: {
     getFullName() { return `${this.firstName} ${this.lastName}`; }
   }

   // GOOD
   const fullName = computed(() => `${firstName.value} ${lastName.value}`);
   ```

2. **Filtering/sorting in methods** called from template bindings.

### Agent rules

- Convert template-called methods that only read reactive data into `computed` properties.

---

## Category 5 — Component Lazy Loading (Nuxt + Vue Router)

### Why it matters

Loading all components upfront increases the initial bundle size. In Nuxt, route-level code splitting is automatic — but heavy components used within a page can still bloat the initial chunk.

### What to look for

1. **Heavy Vue components imported synchronously** when they're only conditionally shown:
   ```ts
   // BAD
   import HeavyChart from "./HeavyChart.vue";

   // GOOD
   const HeavyChart = defineAsyncComponent(() => import("./HeavyChart.vue"));
   ```

2. **Nuxt: pages that disable SSR for the whole page** when only a specific section needs it:
   ```html
   <!-- BAD: disables SSR for entire page -->
   <ClientOnly>
     <EntirePage />
   </ClientOnly>

   <!-- GOOD: wrap only the browser-only sub-section -->
   <ClientOnly>
     <MapWidget />
   </ClientOnly>
   ```

3. **Nuxt: missing `lazy` prefix on heavy auto-imported components** — e.g. `<LazyHeavyModal>` instead of `<HeavyModal>`.

### Agent rules

- Wrap heavy components with `defineAsyncComponent` when used conditionally.
- In Nuxt, suggest `<Lazy>` prefix for components that aren't shown on initial load.

---

## Category 6 — Pinia Store Efficiency

### Why it matters

Pinia is Vue 3's recommended store. Inefficient store usage causes the same re-render problems as Redux without selectors.

### What to look for

1. **Subscribing to the entire store** (destructuring without `storeToRefs`):
   ```ts
   // BAD: `user` is a plain value, not reactive
   const { user } = useUserStore();

   // GOOD: reactive references
   const { user } = storeToRefs(useUserStore());
   ```

2. **Getters that do expensive work and aren't memoized** — Pinia getters are `computed` under the hood, but only if defined as properties, not as methods.

3. **Action side-effects not using `watch`** — actions that read reactive state should use `watch`/`watchEffect` inside the store's `setup()` for reactivity.

### Agent rules

- Replace destructured store values with `storeToRefs(useStore())`.
- Flag store methods called in templates that should be getters (computed).

---

## System Prompt

```
Focus areas for Vue.js / Nuxt:
- Reactivity misuse: reactive() wrapping primitives (use ref() instead); watchEffect that
  assigns derived values to a ref (should be computed); watch/watchEffect with missing
  flush options causing synchronous watchers in hot paths.
- v-if vs v-show: v-if on elements that toggle frequently (use v-show); v-show on
  conditionally-rendered sections that are rarely shown (use v-if for lazy mounting).
- List rendering: v-for with :key="index" when items have stable IDs; v-for + v-if on
  the same element (extract filter into computed property).
- computed vs methods: methods called in templates that derive data from reactive state
  (convert to computed properties for caching).
- Component lazy loading: heavy components imported synchronously when conditionally
  shown (use defineAsyncComponent); Nuxt: heavy page sections not wrapped in <ClientOnly>
  or using <Lazy> prefix.
- Pinia: store destructuring without storeToRefs (breaks reactivity); getters implemented
  as methods instead of computed properties.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Reactive misuse fix | Watcher firing count | Vue DevTools |
| v-if → v-show | DOM toggle time (ms) | Chrome Performance tab |
| v-for key fix | List diff time | Vue DevTools |
| computed vs methods | Render count | Vue DevTools |
| Lazy component | Initial bundle size | `vite-bundle-visualizer` |
| Pinia storeToRefs | Component re-render count | Vue DevTools |
