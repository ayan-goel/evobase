# Agent Optimization Strategy — FastAPI

FastAPI is an async Python web framework built on Starlette and Pydantic. It runs on an asyncio event loop (via uvicorn/gunicorn). The performance model mirrors Node.js: blocking the async event loop with synchronous I/O or CPU-bound work causes all concurrent requests to queue up. Additional FastAPI-specific concerns include Pydantic model misuse and dependency injection overhead.

---

## Detection

| Signal | Confidence |
|---|---|
| `fastapi` in `pyproject.toml` / `requirements.txt` | 0.95 |
| `from fastapi import FastAPI` in source | 0.9 |
| `uvicorn` in deps confirms ASGI server | +0.05 |

---

## Category 1 — Blocking the Async Event Loop

### Why it matters

FastAPI runs on asyncio. Any synchronous blocking call in an `async def` endpoint blocks the entire event loop — no other requests can be processed until that call returns. This is the #1 FastAPI performance killer.

### What to look for

1. **Synchronous ORM calls inside `async def` endpoints** (SQLAlchemy non-async):
   ```python
   # BAD: blocks event loop — all requests queue behind this
   @app.get("/users")
   async def get_users(db: Session = Depends(get_db)):
       return db.query(User).all()  # synchronous!

   # GOOD: use async SQLAlchemy (2.0+)
   @app.get("/users")
   async def get_users(db: AsyncSession = Depends(get_async_db)):
       result = await db.execute(select(User))
       return result.scalars().all()
   ```

2. **`requests.get()` / `urllib` calls** inside `async def` — synchronous HTTP clients block the loop:
   ```python
   # BAD
   async def get_external_data():
       response = requests.get("https://api.example.com/data")  # blocking!

   # GOOD: use httpx async client
   async def get_external_data():
       async with httpx.AsyncClient() as client:
           response = await client.get("https://api.example.com/data")
   ```

3. **`time.sleep()`** inside async routes — should be `await asyncio.sleep()`.

4. **`open()` / `os.path.exists()` / `os.listdir()`** for file I/O — use `aiofiles` or `anyio.Path`.

5. **CPU-bound work** (image processing, ML inference, large data transforms) inside `async def` — these can't be made async; they need `run_in_executor`:
   ```python
   # BAD: blocks event loop for CPU-bound work
   async def process_image(data: bytes):
       result = cpu_heavy_transform(data)  # blocks loop

   # GOOD: offload to thread pool
   async def process_image(data: bytes):
       loop = asyncio.get_event_loop()
       result = await loop.run_in_executor(None, cpu_heavy_transform, data)
   ```

### Agent rules

- Flag synchronous DB calls (`.query()`, `.execute()` without `await`) inside `async def` functions.
- Flag `requests.*` calls inside `async def` — suggest `httpx.AsyncClient`.
- Flag `time.sleep()` — suggest `asyncio.sleep()`.
- Flag CPU-bound function calls inside `async def` without `run_in_executor`.

---

## Category 2 — `def` vs `async def` for CPU-bound Routes

### Why it matters

FastAPI has a clever optimization: `def` (sync) endpoints are run in a thread pool automatically, so they don't block the event loop. But `async def` endpoints run on the event loop directly. If you have CPU-bound work, using `def` is actually better than `async def` + `run_in_executor`.

### What to look for

1. **`async def` endpoints that only call synchronous (non-I/O) code** — these would be more efficient as `def`:
   ```python
   # BAD: declared async but does no I/O — blocks loop
   @app.get("/compute")
   async def heavy_compute(n: int):
       return {"result": sum(i * i for i in range(n))}

   # GOOD: def routes run in FastAPI's thread pool
   @app.get("/compute")
   def heavy_compute(n: int):
       return {"result": sum(i * i for i in range(n))}
   ```

2. Conversely, **`def` endpoints that call `httpx`, `asyncpg`, or other async libraries** — these need to be `async def` or the async calls won't work correctly.

### Agent rules

- Flag `async def` endpoints with no `await` expressions — suggest converting to `def`.

---

## Category 3 — Pydantic Model Performance

### Why it matters

Pydantic v2 (the current default) is significantly faster than v1, but some patterns still cause unnecessary overhead: overly permissive validators, complex nested models on every request, and misuse of `model_validate`.

### What to look for

1. **`@validator` / `@field_validator` that re-computes expensive data** on every model instantiation — memoize or pre-compute:
   ```python
   # BAD: parses a regex on every object creation
   @field_validator("pattern")
   @classmethod
   def validate_pattern(cls, v: str) -> str:
       import re
       re.compile(v)  # just to validate — wasteful
       return v
   ```

2. **`model_validate` (parse) called inside tight loops** on raw DB rows — consider using `model_construct` (no validation) when you trust the data source:
   ```python
   # BAD: full validation on trusted DB data
   users = [UserResponse.model_validate(row) for row in db_rows]

   # GOOD: skip validation for trusted internal data
   users = [UserResponse.model_construct(**row) for row in db_rows]
   ```

3. **Deep nested Pydantic models** used as request bodies that force full deserialization of large payloads on every request.

4. **`response_model` set to a complex nested model** when only a subset of fields is actually used — creates unnecessary serialization work.

### Agent rules

- Flag `model_validate` in loops over trusted database results — suggest `model_construct`.
- Flag validators that instantiate heavy objects (compiled regex, connections) — suggest module-level pre-computation.

---

## Category 4 — Dependency Injection Overhead

### Why it matters

FastAPI's `Depends()` system is powerful but can create redundant database queries when the same data is fetched in multiple dependencies in the same request.

### What to look for

1. **Multiple dependencies that each open a separate DB session** per request:
   ```python
   # BAD: two DB sessions per request
   async def get_user(
       user_id: int,
       db1: AsyncSession = Depends(get_db),  # opens session 1
   ): ...

   async def get_permissions(
       user_id: int,
       db2: AsyncSession = Depends(get_db),  # opens session 2
   ): ...

   # GOOD: share the session via a single Depends
   ```
   FastAPI's `Depends` caches within a single request when the same callable is used — but only if it's literally the same callable reference.

2. **Dependencies that query the same user on every endpoint** instead of caching on the request:
   ```python
   # BAD: two DB lookups for current user in guard + business logic
   async def require_admin(current_user: User = Depends(get_current_user)):
       if current_user.role != "admin": raise HTTPException(403)

   @app.get("/admin/users")
   async def list_admin_users(
       _: None = Depends(require_admin),
       current_user: User = Depends(get_current_user),  # fetches AGAIN
   ): ...
   ```

### Agent rules

- Flag endpoints with multiple `Depends(get_current_user)` or identical dependency callables — FastAPI caches these within a request automatically, so this is usually fine, but flag when different callables fetch the same data.
- Flag endpoints that open multiple DB sessions via different `Depends` callables.

---

## Category 5 — Background Tasks vs Celery

### Why it matters

FastAPI's `BackgroundTasks` runs tasks after the response is sent, on the same process. For tasks that could fail, need retry logic, or should scale independently, Celery/ARQ is more appropriate. Using `BackgroundTasks` for heavy work increases memory pressure on the API process.

### What to look for

1. **`BackgroundTasks` used for email sending, webhook delivery, or other retry-worthy operations** — these should be in a task queue:
   ```python
   # Risky: if the process restarts, the email is lost
   @app.post("/signup")
   async def signup(background_tasks: BackgroundTasks):
       background_tasks.add_task(send_welcome_email, user.email)

   # GOOD for best-effort tasks; for critical ones, use Celery
   ```

2. **`BackgroundTasks` doing heavy CPU work** — runs on the same event loop thread and can block it.

### Agent rules

- Flag `BackgroundTasks` used for email/SMS/webhook delivery with no retry logic — suggest Celery or ARQ.
- Flag `BackgroundTasks` with CPU-intensive code — suggest `run_in_executor` or a proper task queue.

---

## Category 6 — Response Caching

### Why it matters

Endpoints that serve the same data to every user (public API, reference data, read-heavy aggregates) should be cached at the application level, not re-queried on every request.

### What to look for

1. **Endpoints that query the same aggregate data on every request** without any caching:
   ```python
   @app.get("/stats")
   async def get_stats(db: AsyncSession = Depends(get_db)):
       # expensive aggregate query — runs on every request
       count = await db.scalar(select(func.count(User.id)))
       return {"user_count": count}
   ```

2. **Missing `Cache-Control` headers** on public endpoints.

3. **Per-function caching** using `functools.lru_cache` on async functions — `lru_cache` doesn't work correctly with async because it caches the coroutine object, not the result. Should use `aiocache` or `cachetools`.

### Agent rules

- Flag `@lru_cache` on `async def` functions — it caches the coroutine, not the result. Suggest `aiocache` or manual async caching.
- Flag heavy aggregate DB queries in frequently-called endpoints — suggest caching with TTL.

---

## System Prompt

```
Focus areas for FastAPI:
- Async/sync mismatch: synchronous ORM calls (SQLAlchemy .query() / .execute() without
  await) inside async def endpoints; requests.get() instead of httpx.AsyncClient;
  time.sleep() instead of asyncio.sleep(); CPU-bound work in async def without
  run_in_executor.
- def vs async def: async def endpoints with no await expressions (use def instead to
  leverage FastAPI's thread pool for sync code); def endpoints that call async libraries
  (must be async def).
- Pydantic v2: model_validate() in loops over trusted DB data (use model_construct());
  @field_validator that instantiates heavy objects on every call; complex response_model
  with unused nested fields.
- Dependency injection: multiple Depends() callables that each independently query the
  same user/session data per request.
- Background tasks: BackgroundTasks used for retry-worthy operations (email, webhooks)
  without persistence or retry; CPU-bound work in BackgroundTasks.
- Caching: @lru_cache on async functions (caches the coroutine, not the result; use
  aiocache); heavy aggregate queries with no caching strategy.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Sync→async DB | Requests/second | `wrk` / `locust` |
| run_in_executor | Event loop lag (ms) | `uvicorn` metrics / `aiohttp-devtools` |
| model_construct | Serialization time (µs) | `timeit` |
| Caching | DB query count | SQLAlchemy echo logs |
| Background task queue | Task delivery reliability | Celery flower |
