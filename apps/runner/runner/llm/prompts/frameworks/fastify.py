"""Fastify optimization focus areas."""

FOCUS = """
Focus areas for Fastify:

-- Existing patterns --
- Missing schema validation: routes without `schema: { body, querystring, params }`
  defined, losing Fastify's fast JSON serialization and input coercion benefits.
- Synchronous hooks: onRequest/preHandler hooks performing blocking I/O.
- Plugin encapsulation violations: decorators registered on the root fastify
  instance but only needed in a sub-scope.
- async route handlers that swallow errors instead of throwing (breaking Fastify's
  built-in error handler).
- Large route reply objects serialized with JSON.stringify instead of Fastify's
  fast-json-stringify.
- Overuse of setImmediate/process.nextTick deferring that masks real async bugs.

-- Rule catalog (apply low-risk first) --

Rule FY-SCHEMA-001 — Routes without response schema (missing fast serialization)
  Anti-pattern : `fastify.get('/path', async (req, reply) => { return payload })`
                 without a `schema.response` definition
  Detection    : AST — route registration call without `schema: { response: { 200: ... } }`
  Patch (medium): Add JSON Schema for the 200 response; define object shape to
                 enable fast-json-stringify on the happy path
  Validate     : Benchmark before/after (autocannon); schema validation tests
  Rollback if  : response shape varies dynamically in ways schema cannot express
  Do NOT apply : response shape changes dynamically per request

Rule FY-PLUGIN-002 — Decorator registered globally for sub-scope use
  Anti-pattern : `fastify.decorate('someUtil', ...)` in the root scope when
                 only a specific plugin subtree uses it
  Detection    : AST — `fastify.decorate` call in root server file; decorator name
                 only referenced inside specific plugin files
  Patch (medium): Move decoration inside the owning plugin; use plugin-scoped `decorate`
  Validate     : Plugin encapsulation tests; scope isolation checks
  Rollback if  : other plugins unexpectedly rely on the decorator at root scope
  Do NOT apply : decorator genuinely needed across multiple plugin subtrees

Rule FY-AJVCOMP-003 — No custom AJV compiler for reused schemas
  Anti-pattern : Large API with many routes uses Fastify's default AJV instance
                 without caching compiled validators for reused schema objects
  Detection    : file — fastify server instantiation without `ajv: { customOptions }`;
                 more than 20 routes with shared schemas not using `addSchema`
  Patch (medium): Centralise reused schemas via `fastify.addSchema({ $id: 'MySchema', ... })`
                 and reference with `{ $ref: 'MySchema#' }` in route schemas
  Validate     : Cold-start latency; schema compilation overhead profiling
  Rollback if  : schema reference resolution errors
  Do NOT apply : few routes with unique schemas; not worth the abstraction overhead

Rule FY-LOG-004 — Piping pino logs in production through expensive serializers
  Anti-pattern : Fastify's built-in pino logger configured with expensive sync
                 serializers (e.g. pretty-print transport) in production
  Detection    : file — fastify server init with `logger: { transport: { target: 'pino-pretty' } }`
                 not gated to a non-production environment check
  Patch (low)  : Gate pretty printing to dev: `logger: process.env.NODE_ENV !== 'production'
                 ? { transport: { target: 'pino-pretty' } } : true`
  Validate     : Log throughput benchmark; structured JSON in production logs
  Rollback if  : log pipeline requires human-readable format
  Do NOT apply : logging pipeline specifically requires pretty-print format

Rule FY-GRACEFUL-005 — No graceful shutdown handling
  Anti-pattern : Fastify server started with `fastify.listen()` but no
                 `SIGTERM`/`SIGINT` handlers calling `fastify.close()`
  Detection    : file — fastify.listen() call without process.on('SIGTERM'/'SIGINT', ...)
                 calling fastify.close() in server entrypoint
  Patch (low)  : Add:
                   process.on('SIGTERM', async () => { await fastify.close(); process.exit(0); })
  Validate     : Container restart tests; confirm in-flight requests drain
  Rollback if  : graceful shutdown interferes with existing process manager
  Do NOT apply : process manager (PM2 with --kill-timeout) handles this externally
"""
