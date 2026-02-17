# SelfOpt — MVP Overview

## 🚀 Vision

SelfOpt is an autonomous code optimization system.

After a developer connects their GitHub repository, SelfOpt continuously scans the codebase, identifies optimization opportunities, tests potential improvements in a secure sandbox, and presents validated, evidence-backed proposals that can be turned into pull requests with one click.

No setup.
No prompts.
No manual configuration.

Just: connect your repo → come back later → review real improvements.

---

## 🎯 Core Promise

> “We automatically discover, test, and validate optimizations in your codebase — and only surface improvements that actually work.”

SelfOpt:
- Detects tech debt and performance opportunities
- Iteratively tests many candidate fixes
- Validates changes using builds, tests, and benchmarks
- Surfaces only safe, measurable improvements
- Allows developers to open PRs on demand

---

## 🧠 How It Works (High-Level)

### 1. Connect Repository
User installs the GitHub App and selects a repository.

SelfOpt automatically:
- Detects package manager (npm / yarn / pnpm)
- Detects test/build commands
- Identifies framework (Express, NestJS, Next.js, React)
- Creates a reproducible sandbox environment

No manual configuration required (unless detection fails).

---

### 2. Continuous Optimization Engine

SelfOpt runs recurring optimization cycles:

1. **Scan**
   - Analyze AST structure (JS/TS)
   - Identify potential performance and tech debt opportunities
   - Rank candidates by impact and risk

2. **Generate**
   - Create constrained patches (small diffs only)
   - Apply optimization templates + LLM-guided refinements

3. **Validate**
   - Build (if applicable)
   - Run type checks
   - Run tests
   - Run performance checks (benchmark or HTTP mode)

4. **Select**
   - Keep only patches that:
     - Pass all gates
     - Improve measurable metrics
     - Stay within safety constraints

Rejected attempts are logged but never surfaced as proposals.

---

### 3. Evidence & Transparency

When a user returns to the dashboard, they see:

- ✅ “5 optimizations discovered”
- Measurable improvements (e.g., “API latency reduced 8.4%”)
- Exact diff preview
- Risk score
- Before/after metrics
- Full validation logs
- Complete iteration trace (what was tried and discarded)

Each proposal includes a **“Create PR”** button.

SelfOpt does not auto-merge in MVP.

---

## 🛠 Supported Stack (MVP)

### Frameworks
- Express
- NestJS
- Next.js (API + frontend builds)
- React (Vite / CRA / Next frontend)

### Languages
- JavaScript
- TypeScript

### Assumptions
- Repository builds in Linux container
- Tests exist (strongly recommended)
- Node LTS supported

---

## 🔒 Safety & Constraints

To ensure reliability:

- Max 200 lines changed per proposal
- Max 5 files touched
- No dependency upgrades (MVP)
- No config file modifications
- No test modifications
- No secret access during execution
- Sandboxed container with resource limits

Only validated improvements are surfaced.

---

## 📊 Validation Gates

Every candidate patch must pass:

1. Build (if applicable)
2. Typecheck (if applicable)
3. Tests
4. Metric improvement (performance or build-time)
5. Risk heuristics

Performance validation methods:
- Existing benchmark scripts (preferred)
- HTTP microbenchmark mode (fallback)
- Build time measurement (frontend repos)

---

## 🔄 Continuous Mode

SelfOpt runs on a schedule (default nightly).

Each cycle:
- Re-scans repository
- Generates new candidates
- Discards failures
- Surfaces only strong proposals

Budgets enforced:
- Compute minutes/day
- Max proposals per cycle
- Max surfaced optimizations

System automatically pauses if:
- Setup repeatedly fails
- Tests are consistently flaky
- Repo becomes non-runnable

---

## 🖥 Architecture (MVP)

### Control Plane
- Next.js dashboard
- FastAPI backend
- Postgres (state)
- Redis (job queue)
- S3 (artifacts + logs)

### Execution Plane
- Ephemeral sandbox containers (ECS Fargate)
- Reproducible Node environment
- Isolated per-run execution

---

## 📈 Success Criteria (MVP)

The MVP is successful if:

- It produces at least one legitimate optimization in a real repo
- Improvements are measurable (≥3–5% performance delta or meaningful debt reduction)
- No surfaced proposal breaks tests
- PR review takes <5 minutes
- Users trust the evidence

---

## ❌ Out of Scope (MVP)

- Large architectural rewrites
- Dependency upgrades
- Database schema changes
- Multi-language support
- Enterprise RBAC
- Auto-merging

---

## 🔮 Future Expansion (Post-MVP)

- Automated dependency upgrades (with validation)
- Multi-language support (Python, Go)
- Architectural experiment mode
- Memory optimization
- Cost-aware cloud optimization
- Auto-merge under strict policies

---

## 🧩 Product Philosophy

SelfOpt is not an AI autocomplete tool.
It is not a linting tool.
It is not a code review assistant.

It is a continuous engineering improvement system.

It works quietly.
It validates rigorously.
It surfaces only real, measurable wins.

And it runs while you sleep.
