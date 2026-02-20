# Framework Logos — UI Specification

When the runner detects a framework, every surface in the UI that displays that repository should show the corresponding logo/badge. This creates immediate visual recognition and reassures the user that the agent understands their stack.

---

## Icon Asset Strategy

Use **Simple Icons** (https://simpleicons.org/) as the source for all brand icons. They are:
- MIT-licensed SVG files
- Minimal / monochrome — work well as small badges
- Available for every major framework

Store icons in `apps/web/public/framework-icons/` as plain `.svg` files.

### Icon file naming

| Framework identifier (from `DetectionResult.framework`) | File |
|---|---|
| `nextjs` | `nextjs.svg` |
| `react` / `react-vite` | `react.svg` |
| `vue` | `vue.svg` |
| `nuxt` | `nuxt.svg` |
| `angular` | `angular.svg` |
| `svelte` / `sveltekit` | `svelte.svg` |
| `remix` | `remix.svg` |
| `gatsby` | `gatsby.svg` |
| `astro` | `astro.svg` |
| `solidjs` | `solidjs.svg` |
| `express` | `express.svg` |
| `nestjs` | `nestjs.svg` |
| `fastify` | `fastify.svg` |
| `koa` | `nodejs.svg` |
| `trpc` | `trpc.svg` |
| `fastapi` | `fastapi.svg` |
| `django` | `django.svg` |
| `flask` | `flask.svg` |
| `rails` | `rails.svg` |
| `go` / `gin` / `echo` / `fiber` | `go.svg` |
| `rust` / `axum` / `actix` | `rust.svg` |
| `springboot` | `spring.svg` |
| `(fallback)` | `code.svg` (generic) |

### Package manager icons

| Package manager | File |
|---|---|
| `npm` | `npm.svg` |
| `pnpm` | `pnpm.svg` |
| `yarn` | `yarn.svg` |
| `bun` | `bun.svg` |
| `pip` / `uv` | `python.svg` |
| `cargo` | `rust.svg` |
| `go` | `go.svg` |
| `bundler` (Ruby) | `ruby.svg` |
| `maven` / `gradle` | `java.svg` |

---

## Component: `FrameworkBadge`

A new shared component at `apps/web/components/framework-badge.tsx`.

### Props

```typescript
interface FrameworkBadgeProps {
  framework: string | null;
  packageManager?: string | null;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}
```

### Sizes

| size | Icon size | Label |
|---|---|---|
| `sm` | 14×14px | Hidden (tooltip only) |
| `md` | 20×20px | Shown next to icon |
| `lg` | 32×32px | Shown below icon |

### Behavior

- Falls back to `code.svg` if the framework identifier is unrecognised.
- Shows a Radix `Tooltip` with the human-readable framework name on hover (e.g. "Next.js 14", "FastAPI").
- The icon is coloured using the framework's brand colour (pulled from a static map — same colours used by Simple Icons).
- Uses `next/image` with explicit `width`/`height` to avoid layout shift.

### Human-readable label map

```typescript
const FRAMEWORK_LABELS: Record<string, string> = {
  nextjs: "Next.js",
  react: "React",
  "react-vite": "React + Vite",
  vue: "Vue.js",
  nuxt: "Nuxt",
  angular: "Angular",
  svelte: "Svelte",
  sveltekit: "SvelteKit",
  remix: "Remix",
  gatsby: "Gatsby",
  astro: "Astro",
  solidjs: "Solid.js",
  express: "Express",
  nestjs: "NestJS",
  fastify: "Fastify",
  koa: "Koa",
  trpc: "tRPC",
  fastapi: "FastAPI",
  django: "Django",
  flask: "Flask",
  rails: "Ruby on Rails",
  go: "Go",
  gin: "Gin",
  echo: "Echo",
  fiber: "Fiber",
  rust: "Rust",
  axum: "Axum",
  actix: "Actix Web",
  springboot: "Spring Boot",
};
```

---

## Where to Place Badges

### 1. Repository Card (Dashboard)

Location: Bottom-left corner of each `RepoCard`.

```
┌─────────────────────────────┐
│  ayan-goel/my-app           │
│  apps/web                   │
│                             │
│  [Next.js icon] Next.js     │
└─────────────────────────────┘
```

- Use `size="sm"` with `showLabel={true}` for the framework.
- Show package manager as a muted secondary badge (e.g. "pnpm") to the right.
- Data comes from `RepoResponse.framework` (need to add this field — see [detector-improvements.md](detector-improvements.md)).

### 2. Repository Detail Page (`/repos/[repoId]`)

Location: Subtitle row under the repo name, alongside the branch/SHA info.

```
ayan-goel/my-app
[Next.js icon] Next.js   [pnpm icon] pnpm   main @ abc1234
```

- Use `size="md"`.
- Clicking the badge links to the strategy doc (optional future feature).

### 3. Run Card / Run Header

Location: Inside the run row in `RepoRunList`, next to the run status badge.

```
Run #4   [completed]   [Next.js icon]   3 proposals
```

- Use `size="sm"` — icon only, tooltip on hover.
- Data comes from `Run.framework` (need to persist at run-creation time).

### 4. Proposal Card

Location: Not needed — the framework context is already established at the run level.

### 5. Repo Picker (`RepoPicker`)

Location: After a repo is selected and the root dir is entered, auto-detect and show inline.

```
✓ my-app   apps/web   [Next.js icon] Next.js detected
```

- Detected client-side by calling a new `GET /repos/detect` endpoint that accepts `installation_id` + `repo_full_name` + optional `root_dir`.
- Show a loading spinner while detecting.
- This is a "nice to have" — not required for MVP.

---

## Backend Changes Required

To surface framework data in the UI without re-running detection on every page load, the detected framework should be persisted:

1. Add `framework: Optional[str]` and `package_manager: Optional[str]` to the `Repository` DB model.
2. Populate these fields when a run completes detection (write them back to the repo row).
3. Add both fields to `RepoResponse`.

This way the dashboard can show the logo immediately on load without waiting for a run.

### Migration

```sql
ALTER TABLE repositories
  ADD COLUMN IF NOT EXISTS framework TEXT,
  ADD COLUMN IF NOT EXISTS package_manager TEXT;
```

---

## Brand Colour Map

Used to tint the SVG icons (via CSS `filter` or inline `fill`):

```typescript
const FRAMEWORK_COLORS: Record<string, string> = {
  nextjs: "#000000",
  react: "#61DAFB",
  "react-vite": "#646CFF",
  vue: "#4FC08D",
  nuxt: "#00DC82",
  angular: "#DD0031",
  svelte: "#FF3E00",
  sveltekit: "#FF3E00",
  remix: "#000000",
  gatsby: "#663399",
  astro: "#FF5D01",
  solidjs: "#2C4F7C",
  express: "#000000",
  nestjs: "#E0234E",
  fastify: "#000000",
  fastapi: "#009688",
  django: "#092E20",
  flask: "#000000",
  rails: "#CC0000",
  go: "#00ADD8",
  rust: "#CE4A00",
  springboot: "#6DB33F",
};
```

---

## Implementation Steps

1. Download SVG icons for all supported frameworks into `apps/web/public/framework-icons/`.
2. Create `apps/web/lib/framework-meta.ts` with `FRAMEWORK_LABELS`, `FRAMEWORK_COLORS`, and `getFrameworkIconPath(framework: string): string`.
3. Create `apps/web/components/framework-badge.tsx`.
4. Wire `FrameworkBadge` into `RepoCard`, the repo detail page header, and `RepoRunList`.
5. Add DB migration and backend model/schema changes to persist `framework` and `package_manager` on the `Repository`.
6. Update `service.py` to write detected framework back to the repo row after detection.

See [implementation-roadmap.md](implementation-roadmap.md) for sequencing.
