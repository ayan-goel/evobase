# Agent Optimization Strategy — Spring Boot

Spring Boot is the dominant Java (and Kotlin) web framework. It brings together Spring MVC/WebFlux, Spring Data JPA (Hibernate), Spring Security, and an auto-configuration system. Performance concerns are centered around JPA/Hibernate misuse (N+1, lazy loading traps), bean initialization overhead, connection pool tuning, and the `@Transactional` annotation being applied too broadly.

---

## Detection

| Signal | Confidence |
|---|---|
| `spring-boot-starter-parent` in `pom.xml` | 0.95 |
| `org.springframework.boot` plugin in `build.gradle` | 0.95 |
| `@SpringBootApplication` in source | 0.9 |
| `spring-boot-starter-data-jpa` in deps | confirms JPA stack |
| `spring-boot-starter-webflux` | WebFlux (reactive) stack |

---

## Category 1 — JPA / Hibernate N+1 and Lazy Loading Traps

### Why it matters

Hibernate's default fetch strategy for `@OneToMany` and `@ManyToMany` is `LAZY` — associations are loaded on access. Inside a loop this triggers one query per entity. This is the #1 Spring Boot performance problem.

### What to look for

1. **`@OneToMany` / `@ManyToMany` accessed in a loop outside a transaction** — triggers N additional queries or a `LazyInitializationException`:
   ```java
   // BAD: N queries for orders, then N*M queries for order items
   List<Order> orders = orderRepository.findAll();
   for (Order order : orders) {
       System.out.println(order.getItems().size()); // triggers N queries!
   }

   // GOOD: JPQL with JOIN FETCH
   @Query("SELECT o FROM Order o JOIN FETCH o.items")
   List<Order> findAllWithItems();
   ```

2. **`FetchType.EAGER` on `@OneToMany`** — EAGER on a to-many relationship causes Cartesian product joins and loads the entire collection even when you don't need it:
   ```java
   // BAD: always loads all items even for endpoints that don't need them
   @OneToMany(fetch = FetchType.EAGER)
   private List<Item> items;

   // GOOD: keep LAZY, use JOIN FETCH or EntityGraph when needed
   @OneToMany(fetch = FetchType.LAZY)
   private List<Item> items;
   ```

3. **Using `@EntityGraph`** for specific repository methods that need eager loading without making it globally eager.

4. **`findAll()` returning entire table** — should always be paginated:
   ```java
   // BAD: loads all rows
   List<Product> products = productRepository.findAll();

   // GOOD: paginate
   Page<Product> products = productRepository.findAll(PageRequest.of(0, 20));
   ```

### Agent rules

- Flag `@OneToMany` or `@ManyToMany` fields with `fetch = FetchType.EAGER`.
- Flag collection getter calls (`.getItems()`, `.getOrders()`) on entities inside loops.
- Flag `repository.findAll()` calls without pagination where the result is used in a list context.

---

## Category 2 — `@Transactional` Misuse

### Why it matters

`@Transactional` holds a database connection for the duration of the method. Applying it too broadly (on methods that call external APIs or do heavy processing) keeps connections checked out from the pool, causing connection starvation under load.

### What to look for

1. **`@Transactional` on service methods that make external HTTP calls**:
   ```java
   // BAD: holds DB connection while waiting for Stripe API response
   @Transactional
   public PaymentResult chargeCard(String orderId) {
       Order order = orderRepository.findById(orderId).orElseThrow();
       PaymentResult result = stripeClient.charge(order.getAmount()); // blocks connection
       order.setPaymentStatus(result.getStatus());
       orderRepository.save(order);
       return result;
   }

   // GOOD: separate transactions
   public PaymentResult chargeCard(String orderId) {
       Order order = loadOrder(orderId);                     // transaction 1
       PaymentResult result = stripeClient.charge(order.getAmount()); // no transaction
       updateOrderStatus(orderId, result.getStatus());       // transaction 2
       return result;
   }
   ```

2. **`@Transactional(readOnly = true)` not used for read-only service methods** — `readOnly = true` allows Hibernate to skip dirty checking on entities and can use read replicas:
   ```java
   // Missing readOnly hint
   @Transactional
   public List<Product> getAllProducts() { ... }

   // GOOD
   @Transactional(readOnly = true)
   public List<Product> getAllProducts() { ... }
   ```

3. **`@Transactional` on `@Controller` classes** — transactions should be at the service layer, not the controller.

### Agent rules

- Flag `@Transactional` methods that contain external HTTP client calls.
- Flag `@Transactional` (without `readOnly = true`) on methods that only read data.
- Flag `@Transactional` on `@Controller` or `@RestController` classes.

---

## Category 3 — Bean Initialization and Startup Performance

### Why it matters

Spring Boot's auto-configuration eagerly initializes all beans at startup. For large applications this can mean slow cold starts. Lazy initialization defers bean creation until first use.

### What to look for

1. **`@PostConstruct` methods that perform expensive initialization** (loading large datasets, warming caches, making external calls) synchronously at startup — this blocks the application from accepting traffic:
   ```java
   // BAD: loads 100k records before accepting any requests
   @PostConstruct
   public void init() {
       cache = productRepository.findAll(); // blocks startup
   }

   // GOOD: load asynchronously or on first request
   @PostConstruct
   public void init() {
       CompletableFuture.runAsync(() -> {
           cache = productRepository.findAll();
       });
   }
   ```

2. **No `spring.main.lazy-initialization=true`** in `application.properties` for applications with many beans.

3. **Circular bean dependencies** that prevent the application from starting (caught at build time, but should be flagged).

### Agent rules

- Flag `@PostConstruct` methods that call `repository.findAll()` or make external HTTP requests.

---

## Category 4 — Connection Pool Configuration

### Why it matters

Spring Boot uses HikariCP by default — the fastest JDBC connection pool. But the default pool size (10 connections) is often too small for high-traffic applications and too large for serverless/lambda environments.

### What to look for

1. **No `spring.datasource.hikari.*` configuration** in `application.properties` — running with defaults:
   - Default pool size: 10 connections
   - Default connection timeout: 30 seconds (requests queue for 30s before failing!)

2. **`maximumPoolSize` set higher than the database's `max_connections`** — causes connection refusal.

3. **Missing `connectionTimeout` adjustment** — for user-facing requests, fail fast (5s) instead of queuing for 30s.

### Agent rules

- Flag `application.properties` files with no `spring.datasource.hikari.maximum-pool-size` setting.
- Flag `connectionTimeout` values > 10000ms (10s) for synchronous web applications.

---

## Category 5 — DTO Projections

### Why it matters

JPA entities are mapped to full table rows. When an API endpoint only needs 2–3 fields, loading the full entity (with all columns) wastes I/O and memory.

### What to look for

1. **Repository methods returning full entities** when only a projection is needed:
   ```java
   // BAD: loads all 20 columns
   List<User> users = userRepository.findAll();
   return users.stream().map(u -> new UserSummaryDto(u.getId(), u.getName())).toList();

   // GOOD: Spring Data projection interface
   interface UserSummary {
       Long getId();
       String getName();
   }
   List<UserSummary> findAllProjectedBy();
   ```

2. **`@Query` selecting `*` or entire entities** when only a subset is needed.

### Agent rules

- Flag repository methods that return `List<Entity>` where only 2–3 fields are accessed before DTO mapping.

---

## Category 6 — Async and Reactive

### Why it matters

Spring MVC is thread-per-request (blocking). For I/O-heavy endpoints (external API calls, slow queries), blocking threads wastes memory. Spring WebFlux (reactive) or `@Async` methods can improve concurrency.

### What to look for

1. **`RestTemplate` usage** — replaced by `WebClient` (non-blocking) or `RestClient` (Spring 6.1+):
   ```java
   // OLD: blocking, synchronous
   RestTemplate restTemplate = new RestTemplate();
   String result = restTemplate.getForObject(url, String.class);

   // NEW: non-blocking WebClient
   WebClient client = WebClient.create();
   Mono<String> result = client.get().uri(url).retrieve().bodyToMono(String.class);
   ```

2. **Heavy synchronous external API calls** in Spring MVC controllers that block Tomcat threads.

3. **`@Async` methods that return `void`** instead of `CompletableFuture` — exceptions are silently swallowed.

### Agent rules

- Flag `RestTemplate` usage — suggest `WebClient` or `RestClient`.
- Flag `@Async` methods returning `void` — suggest `CompletableFuture<Void>`.

---

## System Prompt

```
Focus areas for Spring Boot:
- JPA/Hibernate N+1: @OneToMany/@ManyToMany getter called inside a loop (missing JOIN
  FETCH or @EntityGraph); FetchType.EAGER on collection associations (causes Cartesian
  product joins); repository.findAll() without pagination.
- @Transactional misuse: methods annotated @Transactional that make external HTTP calls
  (holds DB connection during network I/O); read-only service methods missing
  @Transactional(readOnly = true); @Transactional on @Controller classes.
- Bean initialization: @PostConstruct methods that load large datasets or call external
  APIs synchronously, blocking startup.
- Connection pool: no spring.datasource.hikari configuration (default 10 connections,
  30s timeout inappropriate for most workloads).
- DTO projections: repository methods returning full entities when only 2-3 fields are
  used before DTO mapping (use Spring Data projection interfaces or @Query SELECT dto).
- Async: RestTemplate usage (deprecated, blocking; use WebClient or RestClient);
  @Async methods returning void (exceptions silently dropped; return CompletableFuture).
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| N+1 fix | Query count per request | Hibernate statistics / p6spy |
| @Transactional scope | DB connection hold time (ms) | HikariCP metrics |
| Connection pool tuning | Connection timeout errors | HikariCP JMX / Actuator |
| DTO projections | Data transfer (bytes) | DB slow query log |
| WebClient adoption | Thread pool utilization | Actuator `/metrics` |
