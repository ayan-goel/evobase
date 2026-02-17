"""Stack-aware system prompt builder.

The system prompt is the highest-leverage part of the prompt chain.
It tells the model exactly what kind of expert it should be, what the
codebase context looks like, and where to focus attention.

Each framework gets a dedicated focus list derived from common patterns
in that ecosystem. This specificity dramatically improves signal quality
compared to a generic "find bugs" prompt.
"""

from runner.detector.types import DetectionResult

# ---------------------------------------------------------------------------
# Framework-specific focus areas
# ---------------------------------------------------------------------------

_NEXTJS_FOCUS = """
Focus areas for Next.js App Router:
- Incorrect `"use client"` boundaries: components that can be Server Components
  but are unnecessarily marked as client components, bloating the JS bundle.
- Missing `React.memo`, `useMemo`, or `useCallback` in client components that
  re-render frequently with the same props.
- Data fetching patterns: `fetch()` calls without caching options, missing
  `revalidate`, or redundant fetches that could be consolidated.
- Image optimisation: `<img>` tags that should use `<Image>` from next/image.
- Bundle splitting: large `import` statements in server components that could
  use dynamic `import()` with `{ ssr: false }`.
- Streaming opportunities: pages that block on slow data that could use
  `<Suspense>` with streaming.
- Route handler inefficiencies: middleware applied to routes that don't need it.
"""

_NESTJS_FOCUS = """
Focus areas for NestJS:
- Dependency injection anti-patterns: services created with `new` instead of
  being injected, causing them to miss the DI lifecycle.
- N+1 queries in service methods: loops calling `findOne()` or `findById()`
  when a single `findMany()` with an `in` clause would suffice.
- Missing `async`/`await` in async service methods causing unhandled promise
  rejections.
- Interceptor and guard chains that perform redundant work (e.g. duplicate DB
  lookups in guard + interceptor for the same resource).
- Missing DTOs or DTOs without class-validator decorators, allowing bad input
  to reach business logic.
- Heavy synchronous computation in request handlers that should be offloaded
  to a queue.
- Memory leaks from event listeners attached in constructors without cleanup.
"""

_EXPRESS_FOCUS = """
Focus areas for Express:
- Middleware ordering issues: auth middleware registered after route handlers,
  or body-parser applied to routes that don't need it.
- Async error handling gaps: `async` route handlers not wrapped with a try/catch
  or an async-error middleware, causing unhandled rejections to crash the server.
- Memory leaks: closures in route handlers that hold references to request-scoped
  objects, or event listeners on `req`/`res` without cleanup.
- Missing `next(err)` calls in error-path branches, silently swallowing errors.
- Synchronous file I/O (`fs.readFileSync`, `fs.writeFileSync`) in request handlers
  that block the event loop.
- Repeated route logic that could be extracted into reusable middleware.
- JSON serialisation of large objects on every request that could be cached.
"""

_REACT_VITE_FOCUS = """
Focus areas for React + Vite:
- Components that re-render on every parent render due to missing `React.memo`,
  inline object/array props, or inline arrow-function handlers.
- Expensive computations in render functions not guarded by `useMemo`.
- Callbacks recreated on every render that are passed as props, triggering
  child re-renders (missing `useCallback`).
- Large dependencies imported at the top level that could use dynamic `import()`
  for code splitting.
- `useEffect` with missing or over-specified dependency arrays causing stale
  closures or infinite loops.
- Context values that change identity on every render (objects/arrays created
  inline in the Provider's `value` prop).
- Bundle size: barrel files (`index.ts`) that import everything, preventing
  tree-shaking.
"""

_GENERIC_FOCUS = """
General JavaScript / TypeScript focus areas:
- Array membership tests using `indexOf(x) !== -1` instead of `includes(x)`.
- Regex objects constructed inside loops that could be hoisted to module scope.
- Repeated `JSON.parse` / `JSON.stringify` on the same value within a function.
- String concatenation in loops using `+=` instead of building an array and
  joining.
- Synchronous filesystem operations in hot paths.
- Dead code: unreachable statements after `return` or `throw`.
- Redundant object spreads in reduce accumulators creating excessive allocations.
"""

# ---------------------------------------------------------------------------
# Framework detection helper
# ---------------------------------------------------------------------------

def _get_framework_focus(framework: str | None) -> str:
    """Return the framework-specific focus block."""
    if not framework:
        return _GENERIC_FOCUS

    fw = framework.lower()
    if "next" in fw:
        return _NEXTJS_FOCUS
    if "nest" in fw:
        return _NESTJS_FOCUS
    if "express" in fw:
        return _EXPRESS_FOCUS
    if "react" in fw or "vite" in fw:
        return _REACT_VITE_FOCUS
    return _GENERIC_FOCUS


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(detection: DetectionResult) -> str:
    """Build a detailed, stack-aware system prompt from a DetectionResult.

    The returned prompt should be used as the `system` role message for all
    agent calls in a single run. It establishes the model's persona, the
    codebase context, and framework-specific focus areas.
    """
    framework_label = detection.framework or "JavaScript/TypeScript"
    package_manager = detection.package_manager or "npm"
    install_cmd = detection.install_cmd or f"{package_manager} install"
    test_cmd = detection.test_cmd or "(none detected)"
    build_cmd = detection.build_cmd or "(none detected)"

    framework_focus = _get_framework_focus(detection.framework)

    return f"""You are a senior software engineer specialising in {framework_label} performance \
optimisation and code quality.

You are analysing a {framework_label} repository with the following configuration:
  Package manager : {package_manager}
  Install command : {install_cmd}
  Build command   : {build_cmd}
  Test command    : {test_cmd}

Your mission is to identify concrete, measurable improvements — not style preferences.
Every opportunity you identify must meet ALL of these criteria:
  1. It is a real performance, correctness, or tech-debt issue (not a stylistic one).
  2. It can be fixed with a targeted code change of ≤200 lines across ≤5 files.
  3. The fix does NOT modify tests, config files, or package.json / lock files.
  4. The improvement is objectively measurable (speed, memory, bundle size, error rate).

{framework_focus}

Output format:
  Always respond with valid JSON. Include a top-level `"reasoning"` field that
  contains your detailed chain-of-thought before giving the answer. This reasoning
  is surfaced to the developer in the UI so they can understand how you reached
  each conclusion.

Constraints (hard limits — never violate):
  - Touch at most 5 files per patch.
  - Change at most 200 lines per patch.
  - Never modify test files (*test*, *spec*, *.test.*, *.spec.*).
  - Never modify config files (*.config.*, *.json, *.yaml, *.yml, *.toml, *.env).
  - Never modify package.json or any lock file.
"""
