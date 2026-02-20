# Detector Improvements Plan

The current detector (`apps/runner/runner/detector/`) only handles JavaScript/TypeScript projects. This document describes how to extend it to cover all target ecosystems.

---

## Current Architecture

```
detector/
├── orchestrator.py     # Runs all sub-detectors, merges results
├── package_json.py     # JS/TS: reads package.json, lock files
├── ci_parser.py        # Reads .github/workflows, .gitlab-ci.yml for command hints
└── types.py            # DetectionResult, CommandSignal dataclasses
```

`orchestrator.py` calls the sub-detectors in priority order and merges `CommandSignal` objects by confidence score. The highest-confidence signal for each field (install, build, test, etc.) wins.

---

## Proposed New Architecture

Add one detector module per ecosystem. Each module exposes a single function:

```python
def detect(repo_dir: Path) -> list[CommandSignal]
```

The orchestrator calls all registered detectors and merges the results.

```
detector/
├── orchestrator.py          # updated to call all sub-detectors
├── types.py                 # unchanged
├── js/
│   ├── package_json.py      # existing, moved here
│   └── ci_parser.py         # existing, moved here (or keep at top level)
├── python/
│   ├── pyproject.py         # reads pyproject.toml (uv, poetry, pip)
│   └── requirements.py      # reads requirements.txt
├── go/
│   └── gomod.py             # reads go.mod
├── rust/
│   └── cargo.py             # reads Cargo.toml
├── ruby/
│   └── gemfile.py           # reads Gemfile, Gemfile.lock
└── jvm/
    ├── maven.py             # reads pom.xml
    └── gradle.py            # reads build.gradle / build.gradle.kts
```

---

## Python Detection (`detector/python/`)

### Detection signals

| File | Signal |
|---|---|
| `pyproject.toml` | Parse `[project.dependencies]` or `[tool.poetry.dependencies]` for framework names |
| `requirements.txt` / `requirements/*.txt` | Scan for `fastapi`, `django`, `flask`, `starlette`, `litestar` |
| `Pipfile` | Scan `[packages]` section |
| `uv.lock` | Presence → package manager is `uv` |
| `poetry.lock` | Presence → package manager is `poetry` |

### Framework detection rules

```python
PYTHON_FRAMEWORK_INDICATORS = [
    ("fastapi", "fastapi"),
    ("django", "django"),
    ("flask", "flask"),
    ("starlette", "starlette"),
    ("litestar", "litestar"),
    ("tornado", "tornado"),
    ("aiohttp", "aiohttp"),
]
```

### Package manager detection

Priority order:
1. `uv.lock` → `uv`, install = `uv sync`
2. `poetry.lock` → `poetry`, install = `poetry install`
3. `Pipfile.lock` → `pipenv`, install = `pipenv install`
4. `requirements.txt` → `pip`, install = `pip install -r requirements.txt`

### Build / test / typecheck commands

| Script type | Detection |
|---|---|
| Test | Check `pyproject.toml` `[tool.pytest.ini_options]` → `pytest`; or `Makefile` targets `test:` |
| Typecheck | Look for `mypy` / `pyright` / `ruff check` in `Makefile`, `pyproject.toml` scripts, or CI |
| Build | Look for `docker build` in `Makefile` / CI, or `python -m build` for packages |

### `DetectionResult` fields for Python

```python
DetectionResult(
    package_manager="uv",          # uv / poetry / pip / pipenv
    install_cmd="uv sync",
    build_cmd=None,                 # usually not applicable for apps
    test_cmd="pytest",
    typecheck_cmd="mypy .",
    bench_cmd=None,
    framework="fastapi",
    confidence=0.9,
    evidence=["pyproject.toml: fastapi>=0.100.0", "uv.lock present"],
)
```

---

## Go Detection (`detector/go/`)

### Detection signals

| File | Signal |
|---|---|
| `go.mod` | Framework name from `require` lines; module name from `module` line |
| `Makefile` | Test/build commands |

### Framework detection rules

```python
GO_FRAMEWORK_INDICATORS = [
    ("github.com/gin-gonic/gin", "gin"),
    ("github.com/labstack/echo", "echo"),
    ("github.com/gofiber/fiber", "fiber"),
    ("github.com/go-chi/chi", "chi"),
    ("github.com/gorilla/mux", "gorilla"),
    ("github.com/go-kit/kit", "go-kit"),
]
# Fallback: if go.mod exists but no web framework → framework = "go"
```

### Package manager

Go modules are the only package manager. `install_cmd = "go mod download"` always.

### Commands

| Type | Command |
|---|---|
| Install | `go mod download` |
| Build | `go build ./...` |
| Test | `go test ./...` |
| Typecheck | `go vet ./...` |
| Bench | `go test -bench=. ./...` |

These are static defaults — override from `Makefile` if present.

---

## Rust Detection (`detector/rust/`)

### Detection signals

| File | Signal |
|---|---|
| `Cargo.toml` | Framework from `[dependencies]` |
| `Cargo.lock` | Presence confirms Rust project |

### Framework detection rules

```python
RUST_FRAMEWORK_INDICATORS = [
    ("axum", "axum"),
    ("actix-web", "actix"),
    ("rocket", "rocket"),
    ("warp", "warp"),
    ("poem", "poem"),
    ("salvo", "salvo"),
    ("tide", "tide"),
]
# Fallback: if Cargo.toml exists → framework = "rust"
```

### Package manager

Cargo is universal. `install_cmd = "cargo fetch"`.

### Commands

| Type | Command |
|---|---|
| Install | `cargo fetch` |
| Build | `cargo build --release` |
| Test | `cargo test` |
| Typecheck | `cargo check` |
| Bench | `cargo bench` |
| Lint | `cargo clippy -- -D warnings` |

---

## Ruby Detection (`detector/ruby/`)

### Detection signals

| File | Signal |
|---|---|
| `Gemfile` | Framework from gem names |
| `Gemfile.lock` | Presence confirms Ruby project |

### Framework detection rules

```python
RUBY_FRAMEWORK_INDICATORS = [
    ("rails", "rails"),
    ("sinatra", "sinatra"),
    ("hanami", "hanami"),
    ("grape", "grape"),
    ("padrino", "padrino"),
]
```

### Package manager

Bundler is universal. `install_cmd = "bundle install"`.

### Commands

| Type | Command |
|---|---|
| Install | `bundle install` |
| Build | `rake assets:precompile` (Rails) / none |
| Test | `bundle exec rspec` or `bundle exec rails test` |
| Typecheck | `bundle exec srb tc` (Sorbet) or `bundle exec steep check` |

Detect which test framework from Gemfile: `rspec` vs `minitest`.

---

## JVM Detection (`detector/jvm/`)

### Maven (`pom.xml`)

Framework indicators:
```xml
<!-- Spring Boot -->
<parent>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-parent</artifactId>
</parent>

<!-- Quarkus -->
<groupId>io.quarkus</groupId>

<!-- Micronaut -->
<groupId>io.micronaut</groupId>
```

Commands:
- Install: `mvn dependency:resolve -q`
- Build: `mvn package -DskipTests`
- Test: `mvn test`

### Gradle (`build.gradle` / `build.gradle.kts`)

Framework indicators: presence of `org.springframework.boot`, `io.quarkus`, `io.micronaut` plugins.

Commands:
- Install: `./gradlew dependencies`
- Build: `./gradlew build -x test`
- Test: `./gradlew test`

### Language detection

Check for `src/main/kotlin` → Kotlin; `src/main/java` → Java.

---

## Updated `DetectionResult` type

Add `language` field to distinguish ecosystems:

```python
@dataclass
class DetectionResult:
    package_manager: Optional[str] = None
    install_cmd: Optional[str] = None
    build_cmd: Optional[str] = None
    test_cmd: Optional[str] = None
    typecheck_cmd: Optional[str] = None
    bench_cmd: Optional[str] = None
    framework: Optional[str] = None
    language: Optional[str] = None          # NEW: "javascript", "python", "go", etc.
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
```

The `language` field drives which system prompt is used when the agent has no framework match.

---

## CI Parser Improvements

The existing `ci_parser.py` reads GitHub Actions workflows to extract commands. It should be extended to:

1. Handle `Makefile` targets as a fallback signal for all ecosystems.
2. Recognise Python tox, nox, and invoke configurations.
3. Recognise `justfile` (the Rust-ecosystem `just` task runner).
4. Recognise `Taskfile.yml` (generic task runner).

---

## Orchestrator Changes

The updated `orchestrator.py` should:

1. Run all ecosystem detectors in parallel (they are read-only).
2. Keep only results with `confidence > 0` — skip ecosystems with no signals.
3. If multiple ecosystems have signals (monorepo), use the one with highest confidence OR the one matching `root_dir`.
4. Write detected `framework` and `language` back to the caller so the API can persist them.

---

## Testing Strategy

Each new detector module needs unit tests. Test fixtures should live in `apps/runner/tests/detector/fixtures/`:

```
fixtures/
├── python-fastapi/
│   ├── pyproject.toml
│   └── uv.lock
├── python-django/
│   └── requirements.txt
├── go-gin/
│   └── go.mod
├── rust-axum/
│   └── Cargo.toml
├── ruby-rails/
│   ├── Gemfile
│   └── Gemfile.lock
└── java-spring/
    └── pom.xml
```

Each fixture should produce a deterministic `DetectionResult` that the test asserts against.
