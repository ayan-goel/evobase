
### Required tests
- `apps/api/tests/test_smoke.py` (API imports, app boots)
- `apps/runner/tests/test_smoke.py` (runner imports)
- `apps/web` basic render test

---

## Phase 1 — Supabase Project + Schema + Migrations

### Goal
Establish Supabase as the source of truth (Postgres + Storage).

### Deliverables
- Supabase CLI local project (`supabase init`)
- SQL migrations for core tables:
  - users, organizations, repositories, runs, baselines, opportunities, attempts, proposals, artifacts, settings
- Seed data (minimal)
- Storage bucket created: `artifacts`
- Policies plan (MVP can start permissive locally, tighten later)

### Files
- `infra/supabase/migrations/*.sql`
- `apps/api/app/db/*` (models + db session)
- `apps/api/app/core/settings.py` (Supabase URL/keys)

### Required tests
- Migration apply test (clean db)
- CRUD integration tests for at least:
  - repositories
  - runs
  - proposals
  - artifacts

---

## Phase 2 — FastAPI Core API (Repos + Runs + Proposals)

### Goal
Create the Control Plane API with clean contracts and strong validation.

### Deliverables
- Auth stub (Supabase Auth integration can come later, but route guards must exist)
- CRUD endpoints:
  - `POST /repos/connect` (create repo record)
  - `GET /repos`
  - `GET /repos/{repo_id}`
  - `POST /repos/{repo_id}/run` (enqueue run)
  - `GET /repos/{repo_id}/runs`
  - `GET /proposals/{proposal_id}`
- Status enums and DB models
- Signed URL generation endpoints for artifacts

### Files
- `apps/api/app/repos/router.py`
- `apps/api/app/runs/router.py`
- `apps/api/app/proposals/router.py`
- `apps/api/app/artifacts/router.py`

### Required tests
- Unit tests for Pydantic schemas
- Integration tests for each endpoint with DB
- Tests for signed URL generation (mock Supabase storage client)

---

## Phase 3 — GitHub App Integration (Connect + Webhooks + PR Creation)

### Goal
Enable repo connection via GitHub App and PR creation workflow.

### Deliverables
- GitHub App setup notes (private key storage, webhook secret)
- Webhook handler:
  - installation events
  - repo selection events (if needed)
- Store `github_repo_id`, default branch
- PR creation endpoint:
  - `POST /repos/{repo_id}/proposals/{proposal_id}/create-pr`

### Files
- `apps/api/app/github/*`
- `apps/api/app/repos/service.py`

### Required tests
- Webhook signature verification unit tests
- Mock GitHub API tests:
  - branch creation
  - commit creation
  - PR open
- Contract test: proposal -> PR payload

---

## Phase 4 — Job System (Redis + Celery) + Run Orchestration

### Goal
Make runs actually happen: API enqueues jobs, workers execute orchestration.

### Deliverables
- Redis configured locally
- Celery worker setup
- Run state machine (minimal):
  - queued -> running -> completed/failed
- A “run baseline only” job type
- Store logs pointers and status updates in DB

### Files
- `apps/api/app/engine/queue.py`
- `apps/api/app/engine/tasks.py`
- `apps/api/app/runs/service.py`

### Required tests
- Unit tests for state transitions
- Integration test: enqueue run -> worker picks up -> run status updated

---

## Phase 5 — Runner v0: Repo Checkout + Command Auto-Detection

### Goal
Runner can clone repo at SHA and detect commands for Node/Next/Nest/Express/React repos.

### Deliverables
- Git checkout in sandbox workspace
- Detect:
  - package manager (pnpm/yarn/npm)
  - install_cmd
  - build_cmd
  - test_cmd
  - typecheck_cmd (optional)
- CI workflow parser (GitHub Actions YAML) + package.json parser
- Output a single JSON config object with confidence + evidence

### Files
- `apps/runner/runner/detector/*`
- `apps/runner/runner/sandbox/*`

### Required tests (lots)
- Golden tests with repo fixtures:
  - nextjs repo fixture
  - nestjs repo fixture
  - express repo fixture
  - react (vite) repo fixture
- YAML parsing edge case tests
- Confidence scoring tests

---

## Phase 6 — Runner v1: Baseline Execution + Artifact Upload to Supabase Storage

### Goal
Runner executes baseline pipeline and uploads artifacts to Supabase Storage.

### Deliverables
- Run:
  - install
  - build (if available)
  - typecheck (if available)
  - tests
- Benchmark mode support (MVP choose one path first):
  - script bench if `bench_cmd` exists
  - else skip bench but still store baseline build/test results
- Upload artifacts:
  - logs.txt
  - baseline.json
  - trace.json
- Store `artifacts` records in Postgres via API callback or direct DB client (prefer API callback)

### Files
- `apps/runner/runner/validator/*`
- `apps/runner/runner/packaging/*`

### Required tests
- Baseline pipeline unit tests (mock subprocess)
- Integration test with local Supabase storage (upload + signed URL retrieval)
- Failure-mode tests:
  - install fails
  - tests fail
  - build fails

---

## Phase 7 — Scanner v0: Opportunity Backlog (AST + Heuristics)

### Goal
Generate a ranked list of opportunities to attempt.

### Deliverables
- tree-sitter-based AST pass (JS/TS)
- ripgrep heuristics pass
- Output: `opportunities[]` with:
  - type, location, rationale, risk estimate
- Store opportunities in DB under the run

### Files
- `apps/runner/runner/scanner/*`

### Required tests
- Golden tests: input file -> expected opportunities
- Regression tests: ensure scanner output stable over time
- Performance test: scanner runtime upper bound on medium repo fixture

---

## Phase 8 — PatchGen v0: Template Library (First 10 Templates)

### Goal
Generate safe patches without LLM dependence.

### Deliverables
- 10 high-signal templates (Node/TS oriented), e.g.:
  - Set membership swap
  - memoize pure function wrapper
  - avoid repeated JSON.parse
  - reduce intermediate arrays in hot loop
  - remove obvious dead code (only if build/typecheck prove unused)
- Patch generator returns unified diff + explanation + touched files list
- Hard constraints enforced:
  - ≤ 5 files
  - ≤ 200 lines changed
  - no config/test/deps changes

### Files
- `apps/runner/runner/patchgen/templates/*`

### Required tests
- For each template:
  - fixture input
  - expected diff output
  - lint/build-safe checks (static)
- Constraint enforcement tests

---

## Phase 9 — Validation v1: Candidate Testing + Acceptance Logic

### Goal
Apply patch -> validate deterministically -> accept/reject.

### Deliverables
- Candidate pipeline:
  1) apply patch
  2) build/typecheck (if available)
  3) tests
  4) (optional) benchmark compare if available
- Acceptance logic:
  - tests must pass
  - if benchmark exists: require ≥3% improvement and beyond noise
  - if no benchmark: allow “tech debt safe improvements” but label lower confidence and keep PR disabled unless user enables
- Record all attempts (accepted + rejected) with reasons

### Files
- `apps/runner/runner/validator/*`

### Required tests
- Unit tests for each gate pass/fail
- Flaky test handling tests (rerun once)
- Metric comparison tests

---

## Phase 10 — Proposal Packaging + Trace Timeline + Storage Bundles

### Goal
Create proposal objects with full evidence, and persist.

### Deliverables
- Proposal JSON schema:
  - summary
  - diff
  - metrics before/after
  - risk score
  - trace timeline (attempts + outcomes)
- Upload proposal artifact bundle to Supabase Storage
- Store `proposals` + `artifacts` in DB

### Files
- `apps/runner/runner/packaging/*`
- `apps/api/app/proposals/*`
- `apps/api/app/artifacts/*`

### Required tests
- Schema validation tests (Pydantic + JSON)
- Golden tests for proposal bundle shape
- Signed URL retrieval tests

---

## Phase 11 — Dashboard v0 (Next.js): Runs + Proposals + Evidence Viewer

### Goal
Users can see everything: runs, proposals, diffs, logs, trace, and create PR.

### Deliverables
Pages:
- `/dashboard` (repos list + run status)
- `/repos/[repoId]` (runs + proposals)
- `/proposals/[proposalId]` (diff viewer, metrics, trace, logs)
- “Create PR” button for proposal

UI components:
- Proposal cards
- Diff viewer (simple text diff is fine MVP)
- Trace timeline (collapsible list)
- Evidence links (logs via signed URLs)

### Files
- `apps/web/app/dashboard/page.tsx`
- `apps/web/app/repos/[repoId]/page.tsx`
- `apps/web/app/proposals/[proposalId]/page.tsx`
- `apps/web/components/*`

### Required tests
- Component tests for proposal cards and diff viewer
- Page rendering tests with mocked API
- Playwright E2E:
  - connect -> see repo -> see proposal -> create PR

---

## Phase 12 — Continuous Scheduling + Budget Enforcement

### Goal
Make it run “forever” safely.

### Deliverables
- Scheduler job (Celery beat) to trigger nightly runs
- Budget settings in DB:
  - compute minutes/day
  - max candidates/run
  - max proposals/run
- Auto pause conditions:
  - setup fails N times
  - tests flaky repeatedly
- UI settings panel (optional MVP-lite)

### Required tests
- Budget enforcement unit tests
- Scheduler integration tests (time-based triggering mocked)
- Auto-pause tests

---

## Phase 13 — LLM Agent Integration

### Goal
Replace the regex/AST scanner and template-based patch generator with multi-provider
LLM agents as the primary intelligence layer. Agents discover opportunities through
smart repo analysis, generate patches with full reasoning traces, and feed into the
existing validation pipeline (Phase 9). Users configure provider and model per-repo.

### Deliverables

#### LLM Provider Layer (`apps/runner/runner/llm/`)
- Abstract `LLMProvider` protocol with `async complete()` method
- OpenAI provider: GPT-4o, GPT-4o-mini, o3-mini
- Anthropic provider: claude-sonnet-4-5, claude-haiku-3-5 (with extended thinking)
- Google provider: gemini-2.0-flash, gemini-1.5-pro
- `LLMConfig`, `LLMMessage`, `LLMResponse`, `ThinkingTrace` types
- `get_provider()` factory function
- Default: `anthropic` / `claude-sonnet-4-5`

#### Stack-Aware Prompt Engineering (`apps/runner/runner/llm/prompts/`)
- `system_prompts.py`: `build_system_prompt(detection)` — framework-specific prompts
  - Next.js: Server Components, RSC boundaries, caching, bundle splitting
  - NestJS: DI efficiency, interceptors, N+1 in service methods
  - Express: middleware ordering, async error handling, memory in closures
  - React+Vite: render frequency, memo/useMemo/useCallback, lazy loading
- `discovery_prompts.py`: file selection prompt + per-file analysis prompt
- `patch_prompts.py`: patch generation prompt with constraint reminders

#### Agent Modules (`apps/runner/runner/agent/`)
- `repo_map.py`: build directory tree (depth 3) + file line counts
- `discovery.py`: 2-stage LLM discovery (file selection → opportunity analysis)
- `patchgen.py`: per-opportunity patch generation with reasoning capture
- `orchestrator.py`: coordinates discovery → patchgen → validation
- All agent outputs carry `ThinkingTrace` (model, reasoning text, token counts)

#### DB + API Changes
- `Settings`: add `llm_provider` and `llm_model` columns
- `Opportunity`: add `llm_reasoning` JSON column (discovery thinking trace)
- `Attempt`: add `llm_reasoning` JSON column (patch generation thinking trace)
- Config: `openai_api_key`, `anthropic_api_key`, `google_api_key`
- New endpoint: `GET /llm/models` — lists available models per provider
- Settings API: expose `llm_provider` and `llm_model` in GET/PUT

#### UI — Agent Reasoning Viewer
- New `AgentReasoning` component: collapsible panel showing reasoning trace
- Proposal detail page: shows discovery + patch reasoning below diff
- Settings form: provider radio group + model dropdown

### Required tests
- LLM provider tests (mocked HTTP, reasoning extraction per provider)
- Prompt content tests (framework keywords, constraint injection)
- Agent discovery tests (mocked LLM responses, opportunity shape)
- Agent patchgen tests (diff extraction, constraint enforcement)
- Orchestrator integration tests (full mock pipeline)
- Settings API tests with LLM fields
- `AgentReasoning` component tests

---

## Phase 14A — API Security Layer

### Goal
Every request that enters the API is validated, traceable, and rate-limited.
No external service dependencies — pure FastAPI middleware work.

### Deliverables
- `CORS` middleware (`allow_origins` from `settings.cors_origins`)
- `RequestIdMiddleware` — injects `X-Request-ID` UUID on every response
- `SecurityHeadersMiddleware` — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`
- `slowapi` rate limiting on `POST /runs` — 10 requests/minute per user (configurable)
- `cors_origins` and `run_rate_limit` added to `Settings`

### Required tests
- Security headers present on all responses
- `X-Request-ID` generated when absent from request
- CORS headers returned on OPTIONS
- 11th run-trigger request returns 429 with `Retry-After`

---

## Phase 14B — Observability

### Goal
Structured logs in every environment, per-run trace IDs for grep-ability,
and Sentry capturing exceptions without leaking secrets.

### Deliverables
- `structlog` JSON logging (JSON in prod, colorful console in dev)
  - Every log line carries `request_id` and `trace_id` from context vars
- `trace_id` column on `Run` model — set from `X-Request-ID` at creation time
- `trace_id` returned in `RunResponse` and logged by Celery worker
- Sentry SDK with `FastApiIntegration`, `SqlalchemyIntegration`, `CeleryIntegration`
  - `send_default_pii=False`
  - `before_send` hook strips `api_key`, `secret`, `password`, `token` values
  - No-op when `SENTRY_DSN` is empty
- `SENTRY_DSN` added to config and `.env.example`

### Required tests
- `trace_id` set on run creation and matches request's `X-Request-ID`
- Sentry `before_send` hook redacts API key values
- `init_sentry` no-ops cleanly when DSN is empty

---

## Phase 14C — Infrastructure Hardening

### Goal
The runner is protected against SSRF and resource exhaustion.
Redis requires a password. Artifact signed URLs are real Supabase calls.

### Deliverables
- `validate_repo_url()` in `sandbox/checkout.py` — blocks non-HTTPS and private CIDR ranges
  (127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, ::1, fc00::/7)
- `apply_resource_limits()` in `sandbox/limits.py` — 512 MB virtual memory cap,
  60 CPU-second cap; used as `preexec_fn` in all subprocess calls
- Redis `--requirepass` in `docker-compose.yml`; `REDIS_PASSWORD` in `.env.example`
- `storage.py` — real Supabase `create_signed_url` call replacing the stub;
  path traversal guard (`..` and null-byte rejection); graceful fallback when unconfigured
- `storage_bucket` added to `Settings`

### Required tests
- SSRF: rejects `http://`, `127.x.x.x`, `10.x.x.x`, `169.254.x.x`; accepts GitHub URLs
- Resource limits: `setrlimit` called with correct values (mocked)
- Storage: `../` path rejected, `None` returned when Supabase unconfigured,
  Supabase client called when key is set (mocked)

---

# Implementation Notes (Cursor Guidance)

## Recommended Cursor workflow
- Work one phase at a time
- For each phase:
  - Implement core logic
  - Add unit tests
  - Add integration tests
  - Update docs
- Do not proceed to the next phase until:
  - tests pass
  - fixtures exist
  - golden tests written for stable behavior

## Golden test fixtures (must create early)
Create minimal repo fixtures for:
- nextjs-ts
- nestjs-ts
- express-ts
- react-vite-ts

These fixtures power:
- detector tests
- scanner tests
- template tests
- end-to-end runner tests

---

# Definition of Done (MVP)

MVP is complete when:

- User connects repo with no manual config (or one fallback prompt max)
- Baseline runs and stores artifacts in Supabase Storage
- System generates and validates multiple attempts
- At least one proposal is surfaced with full evidence + trace
- User can click “Create PR” and PR is created on GitHub
- Continuous nightly runs work with budgets
- Full test suite passes in CI