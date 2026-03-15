"""Generic Python optimization focus areas (Starlette, aiohttp, tornado, Litestar, etc.)."""

FOCUS = """
Focus areas for Python:

-- Existing patterns --
- Blocking I/O in async code: synchronous DB calls, requests.get(), time.sleep(), or
  file I/O inside async def functions — use async equivalents or run_in_executor.
- N+1 queries: relationship attribute access in loops without eager loading
  (select_related / joinedload / prefetch_related).
- Over-fetching: loading full ORM objects when only a few fields are needed
  (use .values(), .only(), or scalar projections).
- Unnecessary computation: list/dict comprehensions that run expensive operations on
  every call when the result could be cached; regex patterns compiled inside functions
  (hoist to module scope).
- Error handling: bare except clauses that swallow exceptions; missing error logging
  before re-raising.
- Memory: large in-memory collections built before streaming; unbounded caches without
  TTL or max size.

-- Rule catalog (apply low-risk first) --

Rule PY-REGEX-001 — Regex compiled inside a function or loop
  Anti-pattern : `re.compile(pattern)` inside a function body or loop, causing
                 the pattern to be recompiled on every call
  Detection    : Python AST — `re.compile(` call inside a function definition
                 (not at module/class scope); or `re.match/search/findall(pattern, ...)`
                 with a non-constant string pattern inside a loop
  Patch (low)  : Hoist `re.compile(pattern)` to module scope as a constant
  Validate     : Unit tests confirming same match behaviour; profiling showing
                 reduced allocation
  Rollback if  : pattern depends on runtime values (must stay in function)
  Do NOT apply : pattern is constructed dynamically from runtime parameters

Rule PY-BARE-EXCEPT-002 — Bare except clause swallowing all exceptions
  Anti-pattern : `except:` or `except Exception:` without re-raising, logging,
                 or narrowing to specific exception types
  Detection    : Python AST — `ExceptHandler` with no exception type (bare except)
                 or type `Exception` whose body does not contain a `raise` or
                 logging call (structlog, logging, print)
  Patch (medium): Narrow to the expected exception type(s); add `logger.exception()`
                 or `logger.error()` before any `pass` or `return` in the handler
  Validate     : Unit tests that verify exception propagation; log output
  Rollback if  : intentional catch-all for resilience; requires manual review
  Do NOT apply : top-level exception boundary (main function, CLI entrypoint) with
                 explicit intent to suppress

Rule PY-BLOCKING-003 — Blocking I/O in async function
  Anti-pattern : `async def f()` calling `requests.get()`, `time.sleep()`,
                 `open()` (sync), or synchronous DB drivers without
                 `asyncio.get_event_loop().run_in_executor()`
  Detection    : Python AST — `async def` function body containing direct calls
                 to `requests.get/post/put/delete`, `urllib.request.urlopen`,
                 `time.sleep`, `open(` (not via aiofiles)
  Patch (medium): Replace with async equivalents (`httpx.AsyncClient`,
                 `asyncio.sleep`, `aiofiles.open`); or wrap sync calls in
                 `await asyncio.to_thread(blocking_fn, *args)`
  Validate     : Load test event loop lag metric; integration tests
  Rollback if  : async equivalents behave differently (e.g. connection pooling)
  Do NOT apply : function is called only at startup/teardown, not in hot path

Rule PY-CACHE-004 — Expensive pure function called repeatedly without memoization
  Anti-pattern : Function with no side effects called multiple times in a loop or
                 request handler with the same arguments; result never stored
  Detection    : Python AST — function call expression in a loop body; called
                 function has no DB/IO/random access; same arguments used each
                 iteration (constant or loop-invariant)
  Patch (low/medium): Add `@functools.lru_cache(maxsize=128)` to the function;
                 or cache the result before the loop: `result = expensive(args)`
  Validate     : Unit tests; profiling call count before/after
  Rollback if  : function has hidden side effects; arguments include unhashable types
  Do NOT apply : function is async (use aiocache instead); arguments are always unique

Rule PY-STREAM-005 — Large file/response loaded entirely into memory
  Anti-pattern : `content = f.read()` or `response.content` for large files/responses
                 before processing; entire dataset loaded into a list before iterating
  Detection    : Python AST — `f.read()` (no size limit) or `.content` attribute
                 on a requests/httpx response; `list(generator)` before iteration
                 in a function that processes large data
  Patch (medium): Replace with chunk-based reading: `for chunk in f.read(8192):`
                 or `response.iter_bytes()`; use generators instead of lists
  Validate     : Memory profiling (memory_profiler) under realistic payload sizes
  Rollback if  : downstream code requires random access to the full content
  Do NOT apply : data must be fully buffered (e.g. hashing, multipart processing)
"""
