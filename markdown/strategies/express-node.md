# Agent Optimization Strategy — Express / Node.js

Express is a minimal Node.js web framework. The underlying runtime (Node.js) is single-threaded and event-loop-based — everything runs on one thread, and blocking it even briefly causes all concurrent requests to queue up. The dominant optimization concerns are event loop health, async error propagation, memory management, and middleware design.

---

## Detection

| Signal | Confidence |
|---|---|
| `express` in deps | 0.85 |
| `server.js` / `app.js` / `src/app.ts` with `express()` | 0.9 |
| No `@angular/core`, `next`, `react` in deps | confirms backend |

---

## Category 1 — Blocking the Event Loop

### Why it matters

Node.js is single-threaded. Any synchronous call that takes more than ~10ms blocks every other request on the server. The most dangerous offenders are synchronous file I/O, large JSON serialization, and CPU-intensive operations in request handlers.

### What to look for

1. **`fs.readFileSync` / `fs.writeFileSync` / `fs.existsSync` in request handlers**:
   ```ts
   // BAD: blocks the event loop for the duration of the disk read
   app.get("/config", (req, res) => {
     const config = fs.readFileSync("./config.json", "utf-8");
     res.json(JSON.parse(config));
   });

   // GOOD: async
   app.get("/config", async (req, res) => {
     const config = await fs.promises.readFile("./config.json", "utf-8");
     res.json(JSON.parse(config));
   });
   ```

2. **`child_process.execSync` / `spawnSync`** in request handlers — always use the async variants.

3. **Large `JSON.stringify` on deeply nested objects** in hot paths — consider streaming JSON serialization (`fast-json-stringify`) for large payloads.

4. **`crypto.pbkdf2Sync`** (password hashing) in request handlers — this is intentionally slow and blocks for ~100ms. Use the async version.

### Agent rules

- Flag all `*Sync` functions called inside Express route handlers or middleware.
- Flag `JSON.stringify` on objects that could be >100KB (arrays of DB results, large configs).

---

## Category 2 — Async Error Handling

### Why it matters

Express's error handling is designed around callbacks. `async` route handlers that throw unhandled rejections crash the process (Node.js < 15) or emit an `unhandledRejection` event that is easy to miss. Every async route needs either try/catch or a wrapper.

### What to look for

1. **`async` route handlers without try/catch** that can throw:
   ```ts
   // BAD: unhandled rejection if db.findUser throws
   app.get("/user/:id", async (req, res) => {
     const user = await db.findUser(req.params.id);
     res.json(user);
   });

   // GOOD: try/catch passes to Express error handler
   app.get("/user/:id", async (req, res, next) => {
     try {
       const user = await db.findUser(req.params.id);
       res.json(user);
     } catch (err) {
       next(err);
     }
   });
   ```

2. **Missing error handling middleware** at the app level:
   ```ts
   // Required: error handler with 4 parameters
   app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
     console.error(err);
     res.status(500).json({ error: "Internal server error" });
   });
   ```

3. **Promises returned from middleware without `return next()`** — Express won't catch rejected promises in middleware unless they call `next(err)`.

4. **Missing `await` before async operations** in route handlers — fire-and-forget database writes that fail silently.

### Agent rules

- Wrap every `async` route handler in try/catch with `next(err)`.
- Flag route handlers that `await` database calls but have no try/catch.
- Flag route files that have no error-handling middleware registration.

---

## Category 3 — Middleware Ordering and Scope

### Why it matters

Express applies middleware in registration order. Expensive middleware (auth checks, body parsing, rate limiting) applied globally wastes work for routes that don't need it.

### What to look for

1. **`express.json()` applied globally** when only a few routes accept JSON bodies:
   ```ts
   // BAD: parses body for ALL routes including GET /health, GET /static/*
   app.use(express.json());

   // BETTER: apply only to routes that need it
   app.use("/api", express.json());
   ```

2. **Auth middleware not registering before the routes it protects** — or applied to routes that should be public (e.g. `/health`, `/metrics`):
   ```ts
   // BAD: health check requires auth
   app.use(requireAuth);
   app.get("/health", (req, res) => res.json({ ok: true }));

   // GOOD
   app.get("/health", (req, res) => res.json({ ok: true })); // public
   app.use(requireAuth); // protects everything after this line
   ```

3. **Repeated validation/auth logic inline in multiple route handlers** instead of middleware.

4. **CORS middleware applied after route handlers** — CORS preflight responses never reach the handler.

### Agent rules

- Flag `express.json()` / `express.urlencoded()` registered on `app` (globally) when most routes are GETs — suggest scoping to `/api`.
- Flag auth middleware registered after route definitions.

---

## Category 4 — Memory Leaks

### Why it matters

Long-running Express servers accumulate memory leaks over time, eventually causing OOM crashes. The most common sources are event listeners that are never removed, closures that hold large objects, and connection pools that are not properly closed.

### What to look for

1. **Event listeners added in route handlers** without removal:
   ```ts
   // BAD: adds a new listener on every request, never removed
   app.post("/subscribe", (req, res) => {
     eventEmitter.on("data", (data) => {
       res.write(JSON.stringify(data));
     });
   });
   ```

2. **Caches implemented as plain objects or Maps** in module scope that grow unboundedly — no eviction policy.

3. **Large request body accumulation** — req body attached to session or closure and never released.

4. **Database connection creation inside route handlers** instead of using a shared pool:
   ```ts
   // BAD: creates a new connection per request (connection exhaustion)
   app.get("/users", async (req, res) => {
     const db = new Pool(config);
     const users = await db.query("SELECT * FROM users");
     res.json(users.rows);
   });
   ```

### Agent rules

- Flag `EventEmitter.on()` calls inside route handlers without cleanup.
- Flag in-memory caches (plain objects/Maps) without size limits — suggest `lru-cache`.
- Flag database connection creation inside route handlers — suggest module-level pool.

---

## Category 5 — Route Handler Design

### Why it matters

Monolithic route handlers that mix HTTP plumbing with business logic are hard to test and often duplicate code.

### What to look for

1. **Business logic duplicated across multiple route handlers** — e.g. the same permission check or data transformation appearing in 3+ handlers.

2. **Route handlers over 50 lines** that mix validation, business logic, and response serialization.

3. **Missing early returns for error conditions** — deeply nested `if/else` chains instead of guard clauses:
   ```ts
   // BAD: deeply nested
   app.get("/user/:id", async (req, res) => {
     if (req.user) {
       if (req.user.id === req.params.id) {
         const user = await db.findUser(req.params.id);
         if (user) {
           res.json(user);
         } else {
           res.status(404).json({ error: "Not found" });
         }
       } else {
         res.status(403).json({ error: "Forbidden" });
       }
     } else {
       res.status(401).json({ error: "Unauthorized" });
     }
   });

   // GOOD: guard clauses
   app.get("/user/:id", async (req, res, next) => {
     if (!req.user) return res.status(401).json({ error: "Unauthorized" });
     if (req.user.id !== req.params.id) return res.status(403).json({ error: "Forbidden" });
     try {
       const user = await db.findUser(req.params.id);
       if (!user) return res.status(404).json({ error: "Not found" });
       res.json(user);
     } catch (err) {
       next(err);
     }
   });
   ```

### Agent rules

- Extract duplicated business logic into service functions.
- Flatten deeply nested if/else chains into guard clauses with early returns.

---

## Category 6 — Response Streaming

### Why it matters

For large datasets (file downloads, reports, database dumps), buffering the entire response in memory before sending it creates a peak memory spike. Streaming sends data as it becomes available.

### What to look for

1. **Reading a large file into memory before sending**:
   ```ts
   // BAD: loads entire file into RAM
   app.get("/download/:file", (req, res) => {
     const data = fs.readFileSync(`./files/${req.params.file}`);
     res.send(data);
   });

   // GOOD: streams directly
   app.get("/download/:file", (req, res) => {
     const stream = fs.createReadStream(`./files/${req.params.file}`);
     stream.pipe(res);
   });
   ```

2. **Large database result sets loaded entirely into memory** before JSON serialization.

### Agent rules

- Replace `fs.readFileSync` + `res.send` with `fs.createReadStream().pipe(res)` for file downloads.

---

## System Prompt

```
Focus areas for Express / Node.js:
- Event loop blocking: *Sync file system calls (readFileSync, writeFileSync, existsSync)
  in request handlers; child_process.execSync/spawnSync; crypto.*Sync (pbkdf2Sync);
  large JSON.stringify of deeply nested objects.
- Async error handling: async route handlers without try/catch and next(err); missing
  global error handling middleware (4-parameter (err, req, res, next) handler); Promises
  returned from middleware without next(err) on rejection.
- Middleware ordering: body parser / auth middleware applied globally instead of scoped
  to specific route prefixes; auth middleware registered after the routes it should
  protect; CORS middleware registered after route handlers.
- Memory leaks: EventEmitter.on() inside route handlers without removal; unbounded
  in-memory caches (plain objects/Maps with no eviction); database connections created
  per-request instead of using a shared pool.
- Response streaming: large files read with readFileSync and sent with res.send()
  instead of streaming with createReadStream().pipe(res).
- Route design: duplicated validation/permission logic across handlers (extract to
  middleware or service); deeply nested if/else chains (flatten with guard clauses).
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Sync I/O removal | Event loop lag (ms) | `clinic.js doctor` / `0x` |
| Async error handling | Unhandled rejections | Node.js process warnings |
| Middleware scoping | Middleware execution time | Express timing middleware |
| Memory leak fix | RSS memory growth | `clinic.js heapprofiler` |
| Streaming | Peak RSS during download | `process.memoryUsage()` |
