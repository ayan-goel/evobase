"""Generic Node.js / JavaScript / TypeScript optimization focus areas."""

FOCUS = """
Focus areas for generic Node.js / JavaScript / TypeScript:

-- Existing patterns --
- Event loop blocking: synchronous fs/crypto/child_process calls in hot paths.
- Unhandled promise rejections: missing .catch() or try/catch in async functions
  that are not awaited at the call site.
- Memory leaks: global Maps/Sets/arrays that grow unbounded; event listeners
  added in every request without removal.
- Build / compile: TypeScript `strict: false`; unused code in compiled output;
  missing tree-shaking in bundler config.
- Node.js module anti-patterns: `require()` inside loops; large `node_modules`
  bundled for a serverless/edge environment.
- Graceful shutdown: no SIGTERM / SIGINT handler draining in-flight work before
  `process.exit()`.
- Secrets in environment variables that are logged or serialized into error objects.

-- Rule catalog (apply low-risk first) --

Rule NODE-ASYNC-001 — Fire-and-forget promises without rejection handling
  Anti-pattern : `doWork()` called without `await` or `.catch()`; unhandled-
                 rejection crashes or silently loses errors in Node >= 15
  Detection    : AST — call expression of an async function (returns Promise)
                 whose result is discarded (no `await`, no `.then/.catch`, no
                 assignment to a variable that is later awaited)
  Patch (medium): Add `.catch(err => logger.error(err))` or wrap in void with
                 explicit error boundary; prefer `await` where concurrency allows
  Validate     : Unit tests simulating rejection; `--unhandled-rejections=throw` in CI
  Rollback if  : intentional parallel fan-out patterns are disrupted
  Do NOT apply : caller intentionally defers and has a process-level rejection handler

Rule NODE-STRICT-002 — TypeScript strict mode disabled
  Anti-pattern : `tsconfig.json` with `"strict": false` or individual flags
                 `noImplicitAny: false`, `strictNullChecks: false`
  Detection    : file — tsconfig.json compilerOptions lacks `"strict": true`
                 or explicitly sets strictness flags to false
  Patch (medium): Enable `"strict": true`; fix type errors incrementally or use
                 `// @ts-expect-error` with a comment for deferred fixes
  Validate     : `tsc --noEmit` succeeds; unit tests pass
  Rollback if  : too many type errors require non-trivial fixes
  Do NOT apply : project is in active migration from JavaScript; fix incrementally

Rule NODE-LEAK-003 — Unbounded in-memory cache / growing global collection
  Anti-pattern : Module-level `const cache = new Map()` / `const seen = new Set()`
                 that is populated on requests but never evicted
  Detection    : AST — module-level Map/Set/Array declaration that has `.set()`/`.add()`
                 calls inside request handlers but no `.delete()` / `.clear()` call
  Patch (medium): Replace with LRU cache (lru-cache npm); add TTL-based eviction;
                 or move to an external store (Redis) for multi-instance correctness
  Validate     : Memory usage over 10k request simulation; heap snapshot diff
  Rollback if  : LRU eviction causes correctness bugs (cache miss on hot keys)
  Do NOT apply : cache has bounded size enforced elsewhere

Rule NODE-REQUIRE-004 — require() inside hot loops
  Anti-pattern : `require('module')` called inside a function that runs per-request
                 or in a tight loop (Node.js caches modules, but the lookup and
                 resolve overhead is non-zero and the pattern is confusing)
  Detection    : AST — `require(` call expression inside a function body that is
                 called by route/event handler; not at module top-level
  Patch (low)  : Move `require()` / `import` to the top of the module
  Validate     : Unit tests
  Rollback if  : dynamic module selection (different modules based on runtime value)
  Do NOT apply : module path is truly dynamic at runtime

Rule NODE-ENV-005 — NODE_ENV not set to production in deployed environments
  Anti-pattern : Missing `NODE_ENV=production` in production Dockerfile / deploy config;
                 Express and many frameworks enable dev-only features in non-production mode
  Detection    : file — Dockerfile or deployment config does not set ENV NODE_ENV=production;
                 or package.json start script omits `NODE_ENV=production`
  Patch (low)  : Add `ENV NODE_ENV=production` to Dockerfile; update start script
  Validate     : `echo $NODE_ENV` in container; confirm framework dev-mode features off
  Rollback if  : application uses NODE_ENV for logic that needs to change
  Do NOT apply : custom env var naming convention used instead
"""
