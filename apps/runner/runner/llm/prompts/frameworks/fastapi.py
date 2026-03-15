"""FastAPI optimization focus areas."""

FOCUS = """
Focus areas for FastAPI:

-- Existing patterns --
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

-- Rule catalog (apply low-risk first) --

Rule FA-WORK-001 — Single worker in production
  Anti-pattern : uvicorn started without --workers (or without gunicorn with multiple
                 workers); default single-process deployment that cannot use multiple CPU
                 cores for CPU-bound work
  Detection    : regex — `uvicorn.*main:app` in Procfile/Dockerfile/start script
                 without `--workers` or `-w` flag; no gunicorn wrapping uvicorn
  Patch (medium): Add `--workers N` where N = min(CPU_count * 2, DB_pool_size // workers);
                 or use `gunicorn -k uvicorn.workers.UvicornWorker -w N`
  Validate     : Load test (locust/k6) p95 latency + DB pool metrics
  Rollback if  : DB connection pool exhausted; worker OOM under load
  Do NOT apply : containerized environment with horizontal pod autoscaling preferred
                 over vertical worker scaling; stateful in-process caches

Rule FA-SYNC-002 — Blocking I/O inside async endpoint
  Anti-pattern : `async def endpoint()` calling `requests.get()`, `time.sleep()`,
                 `open()`, synchronous SQLAlchemy `session.execute()`, or any other
                 blocking call directly (not via run_in_executor)
  Detection    : AST — `async def` function body containing calls to known
                 blocking functions: `requests.get/post`, `time.sleep`,
                 `open(` (without `asyncio.open`), sync sqlalchemy `session.execute`
  Patch (medium): Replace with async equivalents:
                 `httpx.AsyncClient`, `asyncio.sleep`, `aiofiles.open`,
                 async sqlalchemy session; or run in executor:
                 `await asyncio.get_event_loop().run_in_executor(None, blocking_fn)`
  Validate     : Load test — compare throughput before/after; confirm no event loop stalls
  Rollback if  : async equivalent introduces correctness differences; thread pool exhausted
  Do NOT apply : function runs once at startup; compute is CPU-bound (use ProcessPoolExecutor)

Rule FA-DEP-003 — Redundant DB queries across sibling Depends() callables
  Anti-pattern : Multiple `Depends()` functions each independently querying
                 `db.get(User, user_id)` or similar for the same resource per request
  Detection    : Python AST — two or more `Depends(...)` parameters in the same
                 endpoint function; each dependency function contains a DB query for
                 the same model type on the same key
  Patch (medium): Consolidate into a single dependency that fetches once and returns
                 the object; downstream deps take the object as a Depends() parameter
  Validate     : DB query count per request (SQLAlchemy event listeners); unit tests
  Rollback if  : dependencies have different transaction/session scoping requirements
  Do NOT apply : dependencies are genuinely independent and modify state separately

Rule FA-PYDANTIC-004 — model_validate() in a loop over trusted DB data
  Anti-pattern : `MyModel.model_validate(row)` called in a loop over ORM rows /
                 database query results where the source data is already trusted
  Detection    : AST — `model_validate(` call inside a `for` loop or list
                 comprehension over a DB query result
  Patch (low/medium): Replace with `MyModel.model_construct(**row)` to skip
                 validation; or use `TypeAdapter.validate_python(rows)` for batch
  Validate     : Unit tests confirming field access still works; profile CPU reduction
  Rollback if  : untrusted data mixed with trusted data in the same loop
  Do NOT apply : data originates from user input or an untrusted external source

Rule FA-CACHE-005 — @lru_cache on an async function
  Anti-pattern : `@functools.lru_cache` or `@cache` decorator applied to an
                 `async def` function — caches the coroutine object, not the result
  Detection    : AST — `@lru_cache` or `@cache` decorator immediately above
                 an `async def` function definition
  Patch (low)  : Replace with aiocache `@cached` decorator; or convert the
                 function to `def` if it wraps a sync call that should be cached
  Validate     : Unit tests confirming cached value is returned (not a coroutine)
  Rollback if  : caching semantics differ from existing behaviour
  Do NOT apply : N/A — this is always a bug when the function is async

Rule FA-N1-006 — N+1 async DB queries in a loop
  Anti-pattern : `async for item in items: result = await db.get(Related, item.fk_id)`
                 — one DB round-trip per item instead of a bulk fetch
  Detection    : AST — `await` expression inside a `for`/`async for` loop where
                 the awaited call is a DB get/query function on the same model
  Patch (medium): Replace with `await db.execute(select(Related).where(Related.id.in_(ids)))`
                 before the loop; map results by ID for lookup
  Validate     : DB query count assertion in tests; integration test correctness
  Rollback if  : bulk fetch semantics differ (e.g. soft-delete filtering)
  Do NOT apply : items are processed sequentially by design (e.g. streaming pipeline)
"""
