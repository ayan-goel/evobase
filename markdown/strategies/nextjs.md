# Agent Optimization Strategy — Next.js

Next.js is a React meta-framework with server-side rendering, static generation, React Server Components, and a file-based router. The most impactful optimizations are around the RSC/client boundary, data fetching patterns, and Core Web Vitals.

---

## Detection

| Signal | Confidence |
|---|---|
| `next` in `package.json` dependencies | 0.85 |
| `next.config.js` / `next.config.ts` exists | 0.9 |
| `app/` directory with `layout.tsx` | 0.95 (App Router confirmed) |
| `pages/` directory | 0.8 (Pages Router) |

Distinguish between **App Router** (Next.js 13+) and **Pages Router** — the optimization strategies differ significantly.

---

## Category 1 — React Server Component (RSC) Boundary Errors

### Why it matters

Every `"use client"` directive adds JavaScript to the browser bundle. Unnecessary client components increase Time to Interactive (TTI) and Largest Contentful Paint (LCP). This is the single highest-leverage optimization in modern Next.js.

### What to look for

1. **Components that only render HTML** — no event handlers, no browser APIs, no hooks — but are marked `"use client"`.
   ```tsx
   "use client"; // WRONG — this never uses any client feature
   export function StaticCard({ title, description }: Props) {
     return <div><h2>{title}</h2><p>{description}</p></div>;
   }
   ```

2. **Leaf components pulled into a client tree because the parent is client** — look for opportunities to "push down" the `"use client"` boundary so the parent remains a Server Component.

3. **Data-fetching components marked `"use client"` using `useEffect + useState`** when they could just be `async` Server Components:
   ```tsx
   // BAD: fetches on client, causes waterfall + flash of loading state
   "use client";
   export function UserProfile({ userId }: Props) {
     const [user, setUser] = useState(null);
     useEffect(() => { fetch(`/api/users/${userId}`).then(...) }, [userId]);
   }

   // GOOD: Server Component, no JS in bundle
   export async function UserProfile({ userId }: Props) {
     const user = await db.users.findOne(userId);
     return <div>{user.name}</div>;
   }
   ```

### Agent rules

- Remove `"use client"` from any component that has no: `useState`, `useEffect`, `useReducer`, `useRef`, `useContext`, event handlers (`onClick`, `onChange`, etc.), or browser-only APIs.
- When a client component imports a sub-component that could be a server component, suggest splitting it out and passing it as `children`.

---

## Category 2 — Data Fetching Patterns

### Why it matters

In App Router, `fetch()` requests in Server Components are deduplicated and cached automatically. Misusing these leads to waterfall requests, stale data, or uncached expensive calls.

### What to look for

1. **`fetch()` without `next: { revalidate }` or `cache: 'force-cache'`** in Server Components — these default to `no-store` in Next.js 15+, causing a fresh network call on every request.
   ```tsx
   // BAD: no caching — makes a fresh call every request
   const res = await fetch("https://api.example.com/products");

   // GOOD: cache for 60 seconds (ISR-style)
   const res = await fetch("https://api.example.com/products", {
     next: { revalidate: 60 },
   });
   ```

2. **Sequential `await` for independent fetches** (waterfall) — should be parallelized with `Promise.all`.
   ```tsx
   // BAD: sequential — 2× latency
   const user = await getUser(id);
   const posts = await getPosts(id);

   // GOOD: parallel
   const [user, posts] = await Promise.all([getUser(id), getPosts(id)]);
   ```

3. **Repeated identical fetches** in the same render tree. Next.js's `fetch` deduplication only works for identical URL+options combinations. If the same data is fetched in multiple components without deduplication, use React's `cache()` wrapper for ORM/database calls.

4. **Missing `<Suspense>` boundaries around slow data** — blocking the entire page render when a sub-section is the slow part.

### Agent rules

- Add `next: { revalidate: N }` to uncached `fetch()` calls based on data freshness requirements (look for "user-specific" vs "shared" data).
- Convert sequential `await` chains for independent resources into `Promise.all`.
- Wrap slow page sections in `<Suspense fallback={<Skeleton />}>` to enable streaming.

---

## Category 3 — Image Optimization

### Why it matters

Unoptimized images are a leading cause of poor LCP scores. Next.js's `<Image>` component handles resizing, format conversion (WebP/AVIF), lazy loading, and prevents layout shift.

### What to look for

1. **`<img>` tags pointing to local or remote images** that should use `next/image`:
   ```tsx
   // BAD
   <img src="/hero.jpg" alt="Hero" />

   // GOOD
   import Image from "next/image";
   <Image src="/hero.jpg" alt="Hero" width={1200} height={600} priority />
   ```

2. **Missing `priority` on above-the-fold images** — the hero image should be preloaded to improve LCP.

3. **Missing `width` and `height`** on `<Image>` — causes layout shift (bad CLS score).

4. **Images loaded in a loop without `loading="lazy"`** — all visible at once on slow connections.

### Agent rules

- Replace `<img>` with `<Image>` for any static or remote image.
- Add `priority` to the first image in a page component.
- Ensure every `<Image>` has explicit `width` and `height`.

---

## Category 4 — Bundle Splitting and Dynamic Imports

### Why it matters

Large dependencies (chart libraries, rich text editors, heavy date libraries) shipped to the client on every page load increase Time to Interactive and First Contentful Paint.

### What to look for

1. **Heavy libraries imported at the top of a client component** that are only used conditionally or after user interaction:
   ```tsx
   // BAD: always loads 300KB chart library
   import { LineChart } from "recharts";

   // GOOD: loads only when component is rendered
   const LineChart = dynamic(() => import("recharts").then(m => m.LineChart), {
     ssr: false,
     loading: () => <Skeleton />,
   });
   ```

2. **Modal or drawer content** that is never shown on initial load but is always bundled.

3. **Third-party scripts** that should use `next/script` with `strategy="lazyOnload"` or `strategy="afterInteractive"` instead of being imported directly.

### Agent rules

- Wrap heavy client-side-only libraries (`recharts`, `react-pdf`, `monaco-editor`, etc.) with `dynamic()` + `{ ssr: false }`.
- Move third-party analytics/chat scripts to `<Script strategy="afterInteractive">`.

---

## Category 5 — React Memoization in Client Components

### Why it matters

Client components that re-render on every parent state change when their props haven't changed waste CPU and can cause visible jank.

### What to look for

1. **Expensive list renders** without `React.memo` — a long list that re-renders because a sibling component's state changed.

2. **Inline object/array/function props** passed to memoized children, defeating memoization:
   ```tsx
   // BAD: creates new object on every render, React.memo won't help
   <Chart options={{ color: "red" }} />

   // GOOD
   const chartOptions = useMemo(() => ({ color: "red" }), []);
   <Chart options={chartOptions} />
   ```

3. **Event handlers recreated on every render** — wrap with `useCallback` when passed as props.

4. **Expensive filtering/sorting computations** in render — wrap with `useMemo`.

### Agent rules

- Add `React.memo()` to list item components that receive stable props.
- Wrap inline object/array/function props in `useMemo`/`useCallback`.
- Move expensive calculations inside `useMemo`.

---

## Category 6 — Middleware and Route Handler Efficiency

### Why it matters

Next.js Middleware runs on every matched request on the edge. Heavy middleware or applying it to routes that don't need it adds latency.

### What to look for

1. **Middleware with no `matcher` config** — runs on every request including static assets.
   ```ts
   // BAD: runs on /_next/static/, /images/, etc.
   export function middleware(req) { ... }

   // GOOD
   export const config = {
     matcher: ["/dashboard/:path*", "/api/:path*"],
   };
   ```

2. **Database calls in Middleware** — the edge runtime has no Node.js APIs. This causes silent failures or errors.

3. **Heavy JSON parsing** in route handlers that could be cached at the module level.

### Agent rules

- Add a `matcher` config to any Middleware that lacks one.
- Flag any database import inside a middleware file as an error.

---

## Category 7 — Metadata and SEO

### Why it matters

Missing or incorrect metadata harms search engine indexing and social sharing previews.

### What to look for

1. **Pages without `export const metadata`** in App Router or `<Head>` in Pages Router.
2. **Static metadata that should be dynamic** (e.g. blog post titles using a hard-coded string instead of the post's title).
3. **Open Graph images missing** — add `opengraph-image.tsx` or `twitter-image.tsx`.

---

## System Prompt Additions

The existing system prompt covers categories 1, 4, and 5. Add:

```
- Data fetching: fetch() calls without `next: { revalidate }` options; sequential awaits
  for independent resources that should use Promise.all; missing Suspense boundaries
  around slow data.
- Image optimisation: <img> tags that should use next/image; missing `priority` on
  above-the-fold images; missing explicit width/height causing CLS.
- Middleware: missing `matcher` config causing middleware to run on all routes including
  static assets; database calls inside middleware.
```

---

## Measurability

| Optimization | Metric | Measurement method |
|---|---|---|
| RSC boundary reduction | JS bundle size (KB) | `next build` output + `@next/bundle-analyzer` |
| Data fetching parallelization | Time to First Byte (TTFB) | Lighthouse / WebPageTest |
| Image optimization | LCP score | Lighthouse |
| Dynamic imports | First Contentful Paint | Lighthouse |
| Memoization | Component render count | React DevTools Profiler |
| Middleware matcher | Middleware latency (ms) | Vercel Analytics |
