"""Spring Boot optimization focus areas."""

FOCUS = """
Focus areas for Spring Boot:

-- Existing patterns --
- JPA/Hibernate N+1: @OneToMany/@ManyToMany getter called inside a loop (missing JOIN
  FETCH or @EntityGraph); FetchType.EAGER on collection associations (causes Cartesian
  product joins); repository.findAll() without pagination — use Page<T> with Pageable.
- @Transactional misuse: methods annotated @Transactional that make external HTTP calls
  (holds DB connection during network I/O); read-only service methods missing
  @Transactional(readOnly = true) — disables dirty checking and allows read replicas;
  @Transactional on @Controller or @RestController classes (belongs at service layer).
- Bean initialization: @PostConstruct methods that call repository.findAll() or make
  external API requests synchronously, blocking application startup.
- Connection pool: no spring.datasource.hikari configuration (default 10 connections,
  30s timeout inappropriate for most workloads); connectionTimeout > 10000ms for
  user-facing synchronous requests.
- DTO projections: repository methods returning List<Entity> when only 2-3 fields are
  accessed before DTO mapping — use Spring Data projection interfaces or @Query SELECT dto.
- Async: RestTemplate usage (deprecated, blocking; use WebClient or RestClient from
  Spring 6.1+); @Async methods returning void (exceptions silently dropped; return
  CompletableFuture<Void> instead).

-- Rule catalog (apply low-risk first) --

Rule SB-N1-001 — JPA N+1 via lazy collection access in a loop
  Anti-pattern : `for (Order order : orders) { order.getItems().size(); }` where
                 `items` is a lazy-loaded @OneToMany and the outer query did not use
                 JOIN FETCH or @EntityGraph
  Detection    : Java/Kotlin AST — getter for a @OneToMany/@ManyToMany field called
                 inside a for-each loop; originating repository method lacks
                 `JOIN FETCH` in @Query or no `@EntityGraph` annotation
  Patch (medium): Add `@EntityGraph(attributePaths = {"items"})` to the repository
                 method; or use JPQL `SELECT o FROM Order o JOIN FETCH o.items`
  Validate     : Hibernate SQL logging (show_sql=true); `assertSelectCount(1)` test
  Rollback if  : JOIN FETCH causes Cartesian product (multiple collection paths);
                 use separate queries with @EntityGraph for multiple bags
  Do NOT apply : access is conditional and usually not needed; parent entities few

Rule SB-TX-002 — @Transactional on a read-only service method
  Anti-pattern : Service method that only reads data annotated `@Transactional`
                 without `readOnly = true` — enables Hibernate dirty checking and
                 second-level cache write lock unnecessarily
  Detection    : Java/Kotlin AST — `@Transactional` (no params) on a method whose
                 body contains no `.save()`, `.delete()`, `.persist()`, `.merge()`
                 or EntityManager write operations
  Patch (low)  : Change to `@Transactional(readOnly = true)`
  Validate     : Integration test confirming reads still work; performance benchmark
  Rollback if  : method later needs write semantics (remove `readOnly` then)
  Do NOT apply : method is part of a larger transaction that needs write semantics

Rule SB-POOL-003 — Unconfigured HikariCP connection pool
  Anti-pattern : `spring.datasource.url` configured but no `spring.datasource.hikari.*`
                 properties — defaults to 10 connections max, 30s connectionTimeout
  Detection    : file — application.properties/yml has datasource config but no
                 `spring.datasource.hikari.maximum-pool-size` or
                 `spring.datasource.hikari.connection-timeout`
  Patch (medium): Add:
                   spring.datasource.hikari.maximum-pool-size=20
                   spring.datasource.hikari.connection-timeout=3000
                   spring.datasource.hikari.idle-timeout=600000
  Validate     : Load test connection pool saturation metrics; p99 latency
  Rollback if  : DB max_connections limit exceeded; pool too large for available memory
  Do NOT apply : pool size already configured via environment variables or secrets manager

Rule SB-PROJ-004 — Repository returning full entities for partial field access
  Anti-pattern : `List<User> findAll()` where only `user.getId()` and `user.getEmail()`
                 are accessed — loads all columns including large BLOBs/CLOBs
  Detection    : Java/Kotlin AST — repository method returning `List<EntityType>`;
                 callers access only 2-3 getter methods on each entity
  Patch (medium): Define a projection interface:
                 `interface UserSummary { Long getId(); String getEmail(); }`
                 Change return type to `List<UserSummary>`
  Validate     : SQL log confirms SELECT id, email instead of SELECT *
  Rollback if  : callers need more fields than projected; dynamic field access
  Do NOT apply : all entity fields are genuinely needed

Rule SB-ASYNC-005 — @Async method returning void (exceptions silently dropped)
  Anti-pattern : `@Async public void sendNotification(...)` — exceptions thrown
                 inside the method are silently discarded; no way to observe errors
  Detection    : Java/Kotlin AST — `@Async` annotation on a method with `void`
                 return type (not CompletableFuture or ListenableFuture)
  Patch (medium): Change return type to `CompletableFuture<Void>`;
                 return `CompletableFuture.completedFuture(null)` at the end;
                 configure `AsyncUncaughtExceptionHandler` as a fallback
  Validate     : Unit test that exception is observable via the future
  Rollback if  : callers do not handle the future return type
  Do NOT apply : fire-and-forget with a process-level error handler configured

Rule SB-RESTTEMPLATE-006 — Deprecated blocking RestTemplate in new code
  Anti-pattern : `new RestTemplate()` or `@Autowired RestTemplate` in service code
                 (RestTemplate is in maintenance mode since Spring 5; blocks a thread
                 per request in non-reactive stacks)
  Detection    : Java/Kotlin AST — `RestTemplate` type reference in a @Service or
                 @Component class; file not in legacy/migration package
  Patch (high) : Advisory — replace with `RestClient` (Spring 6.1+) or `WebClient`
                 (reactive); document migration path
  Validate     : Full integration test suite; confirm no blocking under load
  Rollback if  : reactive dependencies not available; Spring version < 5.0
  Do NOT apply : RestTemplate usage is in a compatibility layer or legacy module
                 explicitly marked for future migration
"""
