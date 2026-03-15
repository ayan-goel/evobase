"""Go optimization focus areas (Go, Gin, Echo, Fiber, Chi, Gorilla, etc.)."""

FOCUS = """
Focus areas for Go:

-- Existing patterns --
- Goroutine leaks: http.Get/http.Post without context timeout; go func() infinite loops
  without ctx.Done() exit path; context.WithCancel/Timeout without defer cancel().
- Memory allocations: string += in loops (use strings.Builder); fmt.Sprintf for simple
  int/float conversion (use strconv); slices created with []T{} when capacity is known
  (pre-allocate with make([]T, 0, n)); large struct returns by value in hot paths.
- Mutex patterns: sync.Mutex on read-heavy maps (use sync.RWMutex for concurrent reads);
  mutex held across database or network I/O; unsynchronized counter increments
  (use sync/atomic).
- Interfaces: interface{}/any parameters in hot paths (use generics in Go 1.18+);
  reflect usage inside loop bodies.
- HTTP handlers: http.Client created per-request (use package-level shared client);
  ioutil.ReadAll without http.MaxBytesReader (unbounded memory); missing defer r.Body.Close().
- Error handling: discarded errors with _; fmt.Errorf without %w (loses error type for
  errors.Is/As); panic for recoverable errors.

-- Rule catalog (apply low-risk first) --

Rule GO-CTX-001 — HTTP calls without a context timeout
  Anti-pattern : `http.Get(url)` or `http.Post(url, ...)` using the default http.Client
                 (no timeout) inside a handler or goroutine
  Detection    : Go AST — `http.Get(` or `http.Post(` call (not on a named client with
                 `Timeout` field set); or `http.Client{}` struct literal without `Timeout`
  Patch (medium): Replace with a package-level `var client = &http.Client{Timeout: 10*time.Second}`;
                 use `client.Do(req)` with a context-carrying request
  Validate     : Integration tests with slow upstream mock; confirm cancellation propagates
  Rollback if  : context propagation breaks caller's timeout expectations
  Do NOT apply : timeout already set at a higher level (gateway, reverse proxy)

Rule GO-GOROUTINE-002 — Goroutine started without an exit condition
  Anti-pattern : `go func() { for { /* no ctx.Done() check */ } }()` — goroutine
                 that loops indefinitely without listening for cancellation
  Detection    : Go AST — goroutine literal containing `for {` (infinite loop)
                 without a `case <-ctx.Done():` in a select statement
  Patch (medium): Add a context parameter and `case <-ctx.Done(): return` in the
                 loop's select; or use a done channel
  Validate     : Race detector (`-race`); context cancellation test
  Rollback if  : goroutine must outlive any individual context (use root context)
  Do NOT apply : goroutine is explicitly designed to run for the process lifetime
                 with a signal-based shutdown

Rule GO-ALLOC-003 — String concatenation with + in a loop
  Anti-pattern : `result += str` inside a loop body building a large string
  Detection    : Go AST — `+=` assignment with a string operand inside a for loop body
  Patch (low)  : Replace with `var b strings.Builder; b.WriteString(str); b.String()`
  Validate     : Benchmark before/after (go test -bench); allocation profile
  Rollback if  : extremely short loop (< 5 iterations) — micro-optimisation not worth it
  Do NOT apply : loop body is trivially short and not in a hot path

Rule GO-MUTEX-004 — sync.Mutex on a read-heavy shared map
  Anti-pattern : `mu sync.Mutex` protecting a map that is read far more than written
  Detection    : Go AST — `sync.Mutex` field in a struct; methods on that struct call
                 `mu.Lock()` for both read-only and write operations
  Patch (medium): Replace `sync.Mutex` with `sync.RWMutex`; use `mu.RLock()/RUnlock()`
                 for read operations, `mu.Lock()/Unlock()` only for writes
  Validate     : Benchmark concurrent reads; race detector test
  Rollback if  : read/write ratio is roughly equal (RWMutex overhead not worth it)
  Do NOT apply : map is write-heavy; or use `sync.Map` if key set is stable and large

Rule GO-ERR-005 — fmt.Errorf without %w wrapping
  Anti-pattern : `fmt.Errorf("msg: " + err.Error())` or `fmt.Errorf("msg: %v", err)`
                 instead of `fmt.Errorf("msg: %w", err)` — loses the error type for
                 `errors.Is` / `errors.As` inspection
  Detection    : Go AST — `fmt.Errorf(` call with a `%v` verb where one of the args
                 is an `error`-typed variable
  Patch (low)  : Replace `%v` with `%w` for the error argument
  Validate     : Unit tests using `errors.Is/As` to verify error unwrapping
  Rollback if  : intentional stripping of error type for security/information-hiding
  Do NOT apply : error is intentionally wrapped in a new error type without %w

Rule GO-BODY-006 — Missing defer r.Body.Close() on HTTP responses
  Anti-pattern : `resp, err := client.Do(req)` or `http.Get(url)` without a
                 `defer resp.Body.Close()` immediately after the nil check
  Detection    : Go AST — `http.Client.Do` or `http.Get` call; variable assigned
                 to a response without a following `defer *.Body.Close()` call
  Patch (low)  : Add `defer resp.Body.Close()` immediately after the nil error check
  Validate     : `go vet`; integration test; file descriptor leak test
  Rollback if  : response body is deliberately kept open for streaming
  Do NOT apply : response is immediately streamed and closed by caller
"""
