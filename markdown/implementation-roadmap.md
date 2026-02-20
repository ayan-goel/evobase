# Implementation Roadmap — Framework Support & Agent Optimization

This roadmap sequences all the work described across the planning docs into implementable phases. Each phase can be shipped independently and provides value on its own.

---

## Overview

```
Phase A  ──►  Phase B  ──►  Phase C  ──►  Phase D
(Detector)    (Prompts)     (UI Logos)    (New langs)
```

Phase A and B can run in parallel. Phase C depends on A (needs `framework` persisted). Phase D builds on A (new detector modules).

---

## Phase A — Persist Detected Framework on Repository

**Goal:** Store the detected `framework` and `package_manager` in the database so the UI can display them without re-running the runner.

**Why first:** Every other phase depends on having these fields available. Without them, the UI can't show logos and the agent can't select the right prompt.

### Tasks

1. **DB Migration** (`infra/supabase/migrations/`)
   ```sql
   ALTER TABLE repositories
     ADD COLUMN IF NOT EXISTS framework TEXT,
     ADD COLUMN IF NOT EXISTS package_manager TEXT;
   ```

2. **Backend model** (`apps/api/app/db/models.py`)
   - Add `framework: Mapped[Optional[str]]` and `package_manager: Mapped[Optional[str]]` to `Repository`.

3. **Write-back in run service** (`apps/api/app/runs/service.py`)
   - After `detect()` returns a `DetectionResult`, update `repo.framework` and `repo.package_manager` in the DB.
   - Only write if the detected value differs from what's stored (avoid dirty writes).

4. **Expose in API** (`apps/api/app/repos/schemas.py` + `apps/api/app/github/router.py`)
   - Add `framework: Optional[str]` and `package_manager: Optional[str]` to `RepoResponse`.
   - Include them in `_build_repo_response()`.

5. **Frontend types** (`apps/web/lib/types.ts`)
   - Add `framework: string | null` and `package_manager: string | null` to `Repository` interface.

6. **Tests**
   - Update `tests/db/test_models.py` to include `framework`, `package_manager` in expected columns.
   - Add a test to `tests/engine/test_pipeline.py` that asserts `framework`/`package_manager` are written after a run.

---

## Phase B — Extend Agent Prompts for All Detected Frameworks

**Goal:** Every framework detected by the current JS/TS detector gets a detailed, research-backed system prompt.

**Current state:** Only Next.js, NestJS, Express, and React+Vite have detailed prompts. Nuxt, Angular, Svelte, Vue, Gatsby, Remix, Fastify, Koa, Hapi fall through to `_GENERIC_FOCUS`.

### Tasks

1. **Add new focus blocks** to `apps/runner/runner/llm/prompts/system_prompts.py`:
   - `_VUE_FOCUS` — based on [strategies/vue-nuxt.md](strategies/vue-nuxt.md)
   - `_NUXT_FOCUS` — Nuxt-specific additions on top of `_VUE_FOCUS`
   - `_ANGULAR_FOCUS` — based on [strategies/angular.md](strategies/angular.md)
   - `_SVELTE_FOCUS` — based on [strategies/svelte-sveltekit.md](strategies/svelte-sveltekit.md)
   - `_SVELTEKIT_FOCUS` — SvelteKit-specific additions
   - `_FASTIFY_FOCUS` — Fastify-specific additions
   - `_GENERIC_NODE_FOCUS` — fallback for `koa`, `hapi`, and other Node servers

2. **Update `_get_framework_focus()`** to map new framework identifiers to their focus blocks.

3. **Tests** for `build_system_prompt()`:
   - Assert that each new framework identifier returns a prompt containing at least one framework-specific term (e.g. `OnPush` for Angular, `v-for` for Vue).

**Reference docs:** See each strategy file in `markdown/strategies/` for the exact focus text.

---

## Phase C — Framework Logo Badges in the UI

**Goal:** Every surface that shows a repository displays the framework icon.

**Depends on:** Phase A (the API must return `framework` on `RepoResponse`).

### Tasks

1. **Download SVG icons** into `apps/web/public/framework-icons/`
   - Source: https://simpleicons.org/
   - Files needed: all icons listed in [framework-logos-ui.md](framework-logos-ui.md)
   - Script to download them all at once:
     ```bash
     # Example — download a few key ones
     cd apps/web/public/framework-icons
     curl -O https://cdn.simpleicons.org/nextdotjs/000000.svg
     mv 000000.svg nextjs.svg
     # ... repeat for each framework
     ```

2. **Create `apps/web/lib/framework-meta.ts`**
   - Export `FRAMEWORK_LABELS: Record<string, string>`
   - Export `FRAMEWORK_COLORS: Record<string, string>`
   - Export `getFrameworkIconPath(framework: string | null): string`

3. **Create `apps/web/components/framework-badge.tsx`**
   - Props: `framework`, `packageManager`, `size`, `showLabel`
   - Uses `next/image` + Radix `Tooltip`
   - Falls back to generic icon for unknown frameworks

4. **Wire `FrameworkBadge` into UI surfaces**
   - `apps/web/app/dashboard/page.tsx` → `RepoCard`: add `<FrameworkBadge size="sm">` bottom of card
   - `apps/web/app/repos/[repoId]/page.tsx` → repo detail header: add `<FrameworkBadge size="md">`
   - `apps/web/components/repo-run-list.tsx` → run row: icon-only `<FrameworkBadge size="sm">`

5. **Tests**
   - Unit test `getFrameworkIconPath` for known and unknown identifiers.
   - Render test for `FrameworkBadge` with `framework="nextjs"` — asserts img src and tooltip text.

---

## Phase D — Multi-Ecosystem Detector

**Goal:** Detect Python, Go, Rust, Ruby, and JVM projects. Enable the agent to run on these stacks.

**Depends on:** Phase A and B architecture (they demonstrate the full detect→prompt→run→write-back pipeline).

This is the biggest phase. Implement one ecosystem at a time, starting with the one most likely to appear in user repos.

### D1 — Python (FastAPI / Django / Flask)

1. **Create `apps/runner/runner/detector/python/`**
   - `pyproject.py`: parse `pyproject.toml` for deps + dev-deps + scripts
   - `requirements.py`: parse `requirements.txt` and `requirements/*.txt` files

2. **Register in `detector/orchestrator.py`**

3. **Add Python system prompts** to `system_prompts.py`:
   - `_FASTAPI_FOCUS` — based on [strategies/fastapi.md](strategies/fastapi.md)
   - `_DJANGO_FOCUS` — based on [strategies/django.md](strategies/django.md)
   - `_FLASK_FOCUS` — based on [strategies/flask.md](strategies/flask.md)
   - `_GENERIC_PYTHON_FOCUS` — fallback

4. **Sandbox: Python install/test execution** (`apps/runner/runner/sandbox/`)
   - Ensure `pip`, `uv`, `poetry`, `pipenv` are available in the worker Docker image.
   - The `Dockerfile.worker` already has Python; just ensure pip/uv are available.

5. **Tests** — fixture directories in `apps/runner/tests/detector/fixtures/python-*/`

### D2 — Go

1. **Create `apps/runner/runner/detector/go/gomod.py`**
   - Parse `go.mod` for module name, Go version, and framework dependencies.

2. **Register in orchestrator**

3. **Add `_GO_FOCUS` system prompt** based on [strategies/go.md](strategies/go.md)

4. **Sandbox: Go toolchain in worker Docker image**
   - Add Go installation to `Dockerfile.worker`.

5. **Tests**

### D3 — Rust

1. **Create `apps/runner/runner/detector/rust/cargo.py`**
   - Parse `Cargo.toml` `[dependencies]` section.

2. **Register in orchestrator**

3. **Add `_RUST_FOCUS` system prompt** based on [strategies/rust.md](strategies/rust.md)

4. **Sandbox: Rust/Cargo in worker Docker image**
   - Add `curl https://sh.rustup.rs | sh -s -- -y` to Dockerfile.

5. **Tests**

### D4 — Ruby / Rails

1. **Create `apps/runner/runner/detector/ruby/gemfile.py`**
   - Parse `Gemfile` for gem names and `Gemfile.lock` for version pinning.

2. **Register in orchestrator**

3. **Add `_RAILS_FOCUS` system prompt** based on [strategies/rails.md](strategies/rails.md)

4. **Sandbox: Ruby/Bundler in worker Docker image**

5. **Tests**

### D5 — JVM (Spring Boot)

1. **Create `apps/runner/runner/detector/jvm/maven.py`** and `gradle.py`

2. **Register in orchestrator**

3. **Add `_SPRINGBOOT_FOCUS` prompt** based on [strategies/spring-boot.md](strategies/spring-boot.md)

4. **Sandbox: Java/Maven/Gradle in worker Docker image**
   - Add JDK installation to `Dockerfile.worker` (only if JVM support is enabled — consider making this opt-in via a build arg to avoid bloating the image).

5. **Tests**

---

## Phase E — UI Framework Detection in Repo Picker

**Goal:** Show the detected framework inline in the `RepoPicker` component after the user selects a repo and enters a `root_dir`.

This requires a new lightweight API endpoint that clones (or shallow-fetches) the repository manifest files and runs detection without starting a full run.

### Tasks

1. **New API endpoint** `POST /repos/detect-framework`
   - Body: `{ installation_id, repo_full_name, root_dir? }`
   - Shallow-clones the repo (depth=1), runs `detector.detect()`, returns `DetectionResult`.
   - Cached: if called for the same repo+root_dir within 1 hour, return cached result.

2. **Frontend hook** `useDetectFramework(repoFullName, rootDir)`
   - Calls the endpoint, shows a loading spinner, then shows `<FrameworkBadge>` with the result.
   - Debounce on `rootDir` changes (500ms).

3. **Wire into `RepoPicker`**
   - After a repo is selected, show detection result inline below the root dir input.

---

## Phase F — Agent Prompt Tuning (Ongoing)

**Goal:** Continuously improve the quality of the agent's proposals by refining prompts based on real-world results.

This is not a one-time phase — it is ongoing. It requires:

1. **Tracking proposal acceptance rates** per framework — which proposals do users accept? Which do they reject?

2. **A/B testing prompt variants** — the system should support multiple prompt variants and measure which produces more accepted proposals.

3. **Per-framework fine-tuning priorities** — derived from the acceptance data. If Rails N+1 proposals are accepted 80% of the time but Rails caching proposals are accepted 20% of the time, focus effort on caching prompt improvement.

4. **Feedback loop into strategy docs** — when a new pattern emerges in user feedback, update the strategy markdown files and the corresponding system prompt.

---

## Recommended Implementation Order

| # | Phase | Effort | Impact | Priority |
|---|---|---|---|---|
| 1 | **A** — Persist framework on repo | Small | Medium | High |
| 2 | **B** — Add missing JS/TS prompts | Medium | High | High |
| 3 | **C** — Framework badge UI | Medium | High | High |
| 4 | **D1** — Python detection + prompts | Large | High | High |
| 5 | **D2** — Go detection + prompts | Medium | Medium | Medium |
| 6 | **D3** — Rust detection + prompts | Medium | Medium | Medium |
| 7 | **E** — Picker inline detection | Medium | Medium | Low |
| 8 | **D4/D5** — Ruby + JVM | Large | Low-Medium | Low |
| 9 | **F** — Prompt tuning | Ongoing | High | Continuous |

---

## Notes for Implementers

- **Phases A, B, C are the MVP** — they close the gap for all existing JS/TS users and set up the infrastructure for everything else.
- **Phase D (new languages) requires changes to the Docker image** — coordinate with infrastructure before starting.
- **The strategy docs in `markdown/strategies/` are the source of truth** for what the agent prompts should say. Don't write prompts from scratch — derive them directly from those documents.
- **Each new detector module must have fixture-based tests** — create minimal files that produce a deterministic `DetectionResult` and assert against it.
- **The agent's constraints (max 200 lines, max 5 files, no test/config modifications) are universal** — do not relax them for any framework.
