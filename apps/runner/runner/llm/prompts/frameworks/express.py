"""Express.js optimization focus areas."""

FOCUS = """
Focus areas for Express.js:

-- Existing patterns --
- Synchronous filesystem/blocking calls in request handlers (fs.readFileSync,
  crypto.pbkdf2Sync, JSON.parse on large buffers) that block the event loop.
- Missing error handling: async route handlers without try/catch or
  asyncHandler wrapper, causing unhandled rejections and 500s.
- No compression middleware for JSON APIs with large response bodies.
- Route parameter validation absent, allowing malformed IDs to reach DB queries.
- Overly permissive CORS config (origin: '*') in production.
- Missing HTTP security headers (no helmet or equivalent).
- N+1 queries in middleware chains that run multiple DB lookups per request.
- Large static assets served by Express instead of a CDN or static file server.

-- Rule catalog (apply low-risk first) --

Rule EXP-ASYNC-001 — Unhandled rejections in async route handlers
  Anti-pattern : `app.get('/path', async (req, res) => { ... })` without
                 try/catch and without an async wrapper utility
  Detection    : AST — `app.get/post/put/delete/use` with async callback not
                 wrapped in a `asyncHandler`/`tryCatch` utility
  Patch (low)  : Wrap with an express-async-errors import or per-route
                 `(req, res, next) => Promise.resolve(handler(req, res)).catch(next)`
  Validate     : Unit tests simulating rejected promises; confirm 500 vs hang
  Rollback if  : error handling semantics change
  Do NOT apply : handlers already have explicit try/catch

Rule EXP-HELMET-002 — Missing security headers
  Anti-pattern : `app.use(...)` chain does not include `helmet()` or equivalent
                 security header configuration
  Detection    : file — main app file (app.js/server.js/index.js) has `express()` call
                 without `require('helmet')` or `import helmet`
  Patch (low/medium): Add `app.use(helmet())` after middleware chain definition
  Validate     : Security header scan (securityheaders.com or local check)
  Rollback if  : breaks inline scripts, CSP conflicts with existing headers
  Do NOT apply : custom security header middleware already present

Rule EXP-COMP-003 — No response compression
  Anti-pattern : JSON API responses not compressed when the app serves large payloads
  Detection    : file — main app file uses `express.json()` but no `compression()`
                 middleware; average response body > 1 kB based on route handlers
  Patch (low)  : Add `app.use(compression())` before routes
  Validate     : Transfer size comparison; TTFB under load
  Rollback if  : reverse proxy already compresses; double-compression causes overhead
  Do NOT apply : static file CDN handles compression; real-time streaming responses

Rule EXP-BLOCK-004 — Synchronous blocking calls on the event loop
  Anti-pattern : `fs.readFileSync`, `crypto.pbkdf2Sync`, `JSON.parse` on large
                 buffers, or `child_process.execSync` called inside a request handler
  Detection    : AST — `Sync` suffix function calls or `JSON.parse` of a variable
                 whose source is a request body/file inside a route handler
  Patch (medium): Replace with async equivalents; for CPU-heavy work delegate to
                 worker threads or a job queue
  Validate     : Load test event loop lag (clinic.js or `--prof`); p99 latency
  Rollback if  : concurrency bugs in async refactor
  Do NOT apply : called only at startup/init outside request context

Rule EXP-CORS-005 — Overly permissive CORS in production
  Anti-pattern : `app.use(cors())` or `cors({ origin: '*' })` in a production app
                 that serves authenticated or sensitive endpoints
  Detection    : file — cors() call without origin restriction in a production-
                 targeting config; or origin: '*' with credentials: true (invalid)
  Patch (medium): Restrict origin to explicit allowlist:
                 `cors({ origin: ['https://app.example.com'] })`
  Validate     : Cross-origin request tests from allowed and disallowed origins
  Rollback if  : legitimate clients blocked
  Do NOT apply : public API intentionally allows all origins; ensure no credentials used
"""
