"""NestJS optimization focus areas."""

FOCUS = """
Focus areas for NestJS:

-- Existing patterns --
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

-- Rule catalog (apply low-risk first) --

Rule NEST-CACHE-001 — Recomputing hot GET responses on every request
  Anti-pattern : Controller GET handlers that return stable (non-auth, non-user-specific)
                 data by hitting the DB or running expensive computation on every call
  Detection    : TS AST — `@Get(` controller method with no `@UseInterceptors(CacheInterceptor)`
                 and a body that calls a service method containing DB queries
  Patch (medium): Add `@UseInterceptors(CacheInterceptor)` at route or controller level;
                 configure `CacheModule.register({ ttl: N })` in the module
  Validate     : Load test (k6/wrk) p95 latency + cache hit rate; freshness tests
  Rollback if  : stale data served; user-specific responses accidentally cached
  Do NOT apply : auth/personalized endpoints; GraphQL field resolvers (known limitation)

Rule NEST-COMP-002 — App-level compression when a reverse proxy is present
  Anti-pattern : `app.use(compression())` in main.ts when Nginx or another
                 reverse proxy already handles compression upstream
  Detection    : file — main.ts contains `compression()` middleware AND
                 there is an nginx.conf / docker-compose proxy definition
  Patch (medium): Remove `app.use(compression())` from main.ts; document that
                 compression is handled at the proxy layer
  Validate     : Transfer size check + CPU usage comparison under load
  Rollback if  : response payloads grow unexpectedly (proxy not actually compressing)
  Do NOT apply : no reverse proxy present; direct internet exposure

Rule NEST-SER-003 — Global ClassSerializerInterceptor on high-throughput routes
  Anti-pattern : `app.useGlobalInterceptors(new ClassSerializerInterceptor(reflector))`
                 applied globally, including to heavy endpoints with large entity graphs
  Detection    : file — main.ts with `useGlobalInterceptors(new ClassSerializerInterceptor`
                 AND controller methods returning large entity objects
  Patch (high) : Narrow interceptor scope — apply `@UseInterceptors(ClassSerializerInterceptor)`
                 only on controllers/routes that need it; use plain DTO mapping on hot paths
  Validate     : Load test p95 CPU and response time
  Rollback if  : incorrect response shapes; API contract breakage
  Do NOT apply : API contract requires consistent class-transformer output everywhere

Rule NEST-LOG-004 — Unstructured or debug-level logging in production
  Anti-pattern : Default NestJS `Logger` without JSON output, or log level set
                 to `debug` / `verbose` in production configuration
  Detection    : file — main.ts uses `new Logger()` without a custom logger;
                 or config has `logger: ['debug', 'verbose']`
  Patch (low/medium): Configure Pino or Winston JSON logger via `app.useLogger()`;
                 set log level to `warn` or `error` in production
  Validate     : Log ingestion pipeline receives structured JSON; no log volume spike
  Rollback if  : logging pipeline is incompatible with new format
  Do NOT apply : compliance requirements mandate specific log format

Rule NEST-ADAPTER-005 — Express adapter for performance-critical service
  Anti-pattern : `NestFactory.create(AppModule)` using the default Express adapter
                 when the service has no Express-specific middleware dependencies
  Detection    : file — main.ts imports from `@nestjs/core` with no
                 `@nestjs/platform-fastify` usage; no Express-specific middleware
  Patch (high) : Advisory only — suggest migration to Fastify adapter
                 (`NestFactory.create<NestFastifyApplication>(AppModule, new FastifyAdapter())`)
  Validate     : Full e2e suite; check all middleware/guards/interceptors are compatible
  Rollback if  : Express-specific middleware incompatibility
  Do NOT apply : repo uses Express-specific packages (express-session, passport-local, etc.)
"""
