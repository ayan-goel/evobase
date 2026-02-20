# Agent Optimization Strategy — Svelte / SvelteKit

Svelte compiles components to vanilla JavaScript at build time — there is no virtual DOM and no runtime framework overhead. This makes many React/Vue performance problems moot, but introduces its own set of optimization opportunities around reactivity declarations, store subscriptions, and SvelteKit's data loading model.

---

## Detection

| Signal | Confidence |
|---|---|
| `svelte` in deps | 0.85 → `svelte` |
| `@sveltejs/kit` in deps | 0.95 → `sveltekit` |
| `svelte.config.js` exists | 0.9 |
| `src/routes/` directory | confirms SvelteKit |

---

## Category 1 — Reactive Declarations (`$:`)

### Why it matters

Svelte's `$:` reactive statement re-runs whenever any variable it reads changes. This is powerful but can cause unexpected re-computation if the statement reads too many variables or if dependencies are not clearly scoped.

### What to look for

1. **Reactive statements with side effects** (writing to the DOM, calling APIs) — should be `onMount` or lifecycle functions, not `$:`:
   ```ts
   // BAD: re-fetches every time `userId` or any other variable changes
   $: fetch(`/api/users/${userId}`).then(r => r.json()).then(d => data = d);

   // GOOD: explicit with proper async handling
   $: { if (userId) loadUser(userId); }
   async function loadUser(id: string) { ... }
   ```

2. **Reactive assignments that compute large derived arrays** on every tick — these can't be easily cached in Svelte (unlike Vue's `computed`):
   ```ts
   // BAD: re-filters on every state change, even unrelated ones
   $: filtered = items.filter(i => i.active).sort((a, b) => a.name.localeCompare(b.name));

   // In Svelte this is often fine, but if `items` is large and the component
   // has many unrelated state updates, consider a derived store instead.
   ```

3. **Circular reactive dependencies** — `$: a = b + 1; $: b = a - 1;` causes infinite loops. Look for implicit circular refs.

### Agent rules

- Flag `$:` statements that contain `fetch()` or other async side effects — suggest explicit function calls with conditional guards.
- Flag reactive statements that read more than 3–4 independent variables when the computation is expensive.

---

## Category 2 — Store Subscriptions

### Why it matters

Svelte stores with the `$` auto-subscription syntax are convenient, but subscribing to stores in many components that only need a small slice of the store's data causes unnecessary re-renders.

### What to look for

1. **Subscribing to a large store to read one field**:
   ```ts
   // BAD: subscribes to entire user store, re-renders on any user change
   import { userStore } from "$lib/stores";
   $: name = $userStore.profile.displayName;

   // GOOD: derived store — only re-renders when displayName changes
   import { derived } from "svelte/store";
   const displayName = derived(userStore, $u => $u.profile.displayName);
   ```

2. **Manual `subscribe` calls without `unsubscribe` in `onDestroy`**:
   ```ts
   // BAD: memory leak
   myStore.subscribe(value => console.log(value));

   // GOOD: auto-subscription in template ($myStore) or manual cleanup
   const unsub = myStore.subscribe(value => doSomething(value));
   onDestroy(unsub);
   ```

3. **Writable stores used where `readable` or `derived` would be semantically correct** — not a performance issue, but a correctness/clarity issue worth flagging.

### Agent rules

- Flag manual `subscribe()` calls without corresponding `onDestroy` cleanup.
- Suggest `derived()` when a component reads only a sub-field of a large store.

---

## Category 3 — SvelteKit `load` Functions

### Why it matters

SvelteKit has two types of `load` functions: server loads (`+page.server.ts`) and universal loads (`+page.ts`). Using the wrong type defeats SSR or sends sensitive data to the client.

### What to look for

1. **Database/ORM queries in a universal `+page.ts` `load` function** instead of a server `+page.server.ts`:
   ```ts
   // BAD: runs on both server and client, exposes DB logic + potentially leaks env vars
   // +page.ts
   export async function load() {
     const db = createDbClient(process.env.DATABASE_URL);
     return { users: await db.users.findMany() };
   }

   // GOOD: server-only, never runs in browser
   // +page.server.ts
   export async function load({ locals }) {
     return { users: await locals.db.users.findMany() };
   }
   ```

2. **Sequential `await` calls for parallel data** in `load` functions:
   ```ts
   // BAD: 2× latency
   const user = await getUser(params.id);
   const posts = await getUserPosts(params.id);

   // GOOD
   const [user, posts] = await Promise.all([getUser(params.id), getUserPosts(params.id)]);
   ```

3. **Not using `depends()` for cache invalidation** — SvelteKit load functions are cached but stale data can result from missing `depends` declarations.

4. **`fetch` in server `load` without setting appropriate caching** (using the SvelteKit-enhanced `fetch` which inherits request headers).

### Agent rules

- Flag DB/ORM calls in `+page.ts` (universal) load functions — suggest moving to `+page.server.ts`.
- Convert sequential awaits for independent resources to `Promise.all`.

---

## Category 4 — `{#each}` and Keyed Blocks

### Why it matters

Svelte's `{#each}` renders lists. Like React's `key` prop, Svelte requires a key expression to avoid incorrect DOM recycling when the list order changes.

### What to look for

1. **`{#each}` without a key expression** when items can be reordered:
   ```html
   <!-- BAD: Svelte recycles DOM nodes incorrectly on reorder -->
   {#each items as item}
     <Item {item} />
   {/each}

   <!-- GOOD: key expression -->
   {#each items as item (item.id)}
     <Item {item} />
   {/each}
   ```

2. **Large `{#each}` lists without virtualization** — consider `svelte-virtual-list` for hundreds of items.

### Agent rules

- Add key expression `(item.id)` to `{#each}` blocks over objects with unique IDs.

---

## Category 5 — Component Lazy Loading

### Why it matters

SvelteKit does automatic route-level code splitting. But heavy components used within a route still end up in the route's chunk. Dynamic imports defer loading until the component is needed.

### What to look for

1. **Heavy components imported statically** that are only shown conditionally:
   ```ts
   // BAD
   import HeavyEditor from "./HeavyEditor.svelte";

   // GOOD
   <script>
     let HeavyEditor;
     $: if (showEditor && !HeavyEditor) {
       import("./HeavyEditor.svelte").then(m => HeavyEditor = m.default);
     }
   </script>
   ```

2. **Using `svelte:component` with dynamic imports** — the official pattern for lazy Svelte components.

### Agent rules

- Flag heavy Svelte component imports (`monaco-editor`, chart libraries) that are rendered inside `{#if}` blocks — suggest dynamic import.

---

## Category 6 — Transitions and Animations

### Why it matters

Svelte has built-in `transition:` directives. Using CSS `transition` properties on elements that change layout properties (`width`, `height`, `top`, `left`) causes layout thrashing. Svelte's `animate:` for `{#each}` keyed blocks is more performant.

### What to look for

1. **CSS transitions on `width` / `height` / `top` / `left`** instead of `transform` / `opacity` (which only trigger composite):
   ```css
   /* BAD: triggers layout + paint */
   .item { transition: width 0.3s; }

   /* GOOD: composite-only */
   .item { transition: transform 0.3s; }
   ```

2. **`{#each}` blocks that animate item repositioning without `animate:flip`**:
   ```html
   <!-- Enables smooth reorder animation with FLIP technique -->
   {#each items as item (item.id)}
     <div animate:flip={{ duration: 300 }}>{item.name}</div>
   {/each}
   ```

---

## System Prompt

```
Focus areas for Svelte / SvelteKit:
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
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Reactive declaration | Component update count | Svelte DevTools |
| Derived stores | Re-render count | Svelte DevTools |
| Load function parallelization | TTFB | Lighthouse / WebPageTest |
| Each key | List update time | Chrome Performance |
| Lazy component | Initial chunk size | SvelteKit build output |
| Composite CSS transition | Frame rate (fps) | Chrome DevTools Layers |
