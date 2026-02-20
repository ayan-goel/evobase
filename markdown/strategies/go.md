# Agent Optimization Strategy — Go

Go is a compiled, statically typed language with goroutines, channels, and a garbage collector. Performance patterns in Go are fundamentally different from scripting languages — issues are often about memory allocation pressure (which drives GC pauses), goroutine leaks, mutex contention, and interface overhead. Go programs are already fast by default; the agent should focus on correctness first (goroutine leaks, data races) then allocation reduction.

---

## Detection

| Signal | Confidence |
|---|---|
| `go.mod` exists | 0.9 |
| `go.sum` exists | +0.05 |
| `gin-gonic/gin` in `go.mod` | framework = `gin` |
| `labstack/echo` in `go.mod` | framework = `echo` |
| `gofiber/fiber` in `go.mod` | framework = `fiber` |
| `go-chi/chi` in `go.mod` | framework = `chi` |

Default commands:
- Install: `go mod download`
- Build: `go build ./...`
- Test: `go test ./...`
- Vet: `go vet ./...`
- Bench: `go test -bench=. -benchmem ./...`

---

## Category 1 — Goroutine Leaks

### Why it matters

Goroutines are cheap to create but they never terminate themselves — they must be explicitly stopped or allowed to exit naturally. A goroutine that blocks forever (waiting on an unbuffered channel, select with no default, or `http.Get` with no timeout) accumulates over time, consuming memory and eventually causing OOM.

### What to look for

1. **HTTP client calls without a timeout context**:
   ```go
   // BAD: hangs forever if server doesn't respond
   resp, err := http.Get("https://api.example.com/data")

   // GOOD: timeout context
   ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
   defer cancel()
   req, _ := http.NewRequestWithContext(ctx, "GET", "https://api.example.com/data", nil)
   resp, err := http.DefaultClient.Do(req)
   ```

2. **Goroutines launched with `go func()`** that have no way to stop:
   ```go
   // BAD: runs forever, no way to stop it
   go func() {
       for {
           doWork()
           time.Sleep(interval)
       }
   }()

   // GOOD: respects context cancellation
   go func(ctx context.Context) {
       ticker := time.NewTicker(interval)
       defer ticker.Stop()
       for {
           select {
           case <-ctx.Done():
               return
           case <-ticker.C:
               doWork()
           }
       }
   }(ctx)
   ```

3. **Blocking channel sends with no receiver** — if the receiver goroutine exits early, the sender blocks forever.

4. **`defer cancel()` missing** after `context.WithCancel` / `context.WithTimeout` — context is never cancelled, leaking resources.

### Agent rules

- Flag `http.Get` / `http.Post` calls without a context — suggest `http.NewRequestWithContext`.
- Flag `go func()` with infinite loops that lack a `ctx.Done()` / `context.Canceled` exit path.
- Flag `context.WithCancel` / `context.WithTimeout` without a corresponding `defer cancel()`.

---

## Category 2 — Memory Allocation Patterns

### Why it matters

Go's GC pauses are proportional to heap pressure. Reducing unnecessary allocations — especially in hot paths — reduces GC work and improves tail latency.

### What to look for

1. **String concatenation with `+` in loops** — creates a new allocation per iteration:
   ```go
   // BAD: O(n²) allocations
   result := ""
   for _, s := range items {
       result += s
   }

   // GOOD: single allocation
   var sb strings.Builder
   for _, s := range items {
       sb.WriteString(s)
   }
   result := sb.String()
   ```

2. **`fmt.Sprintf` in hot paths** — allocates. Use `strconv.Itoa`, `strconv.FormatFloat`, etc. for simple conversions:
   ```go
   // BAD: allocates a formatted string
   s := fmt.Sprintf("%d", n)

   // GOOD: no allocation for small ints
   s := strconv.Itoa(n)
   ```

3. **Slices pre-allocated without capacity** — causes multiple reallocations as elements are appended:
   ```go
   // BAD: reallocates as it grows (amortized, but still wasteful)
   results := []int{}
   for _, item := range items {
       results = append(results, transform(item))
   }

   // GOOD: pre-allocate
   results := make([]int, 0, len(items))
   for _, item := range items {
       results = append(results, transform(item))
   }
   ```

4. **Maps created without `make(map[K]V, hint)`** in hot paths — same reallocation issue.

5. **Returning large structs by value** instead of pointers in hot paths — large struct copies are expensive:
   ```go
   // BAD for large structs (> ~8 fields): copies the whole struct
   func processUser(u User) User { ... }

   // GOOD: pointer avoids copy
   func processUser(u *User) *User { ... }
   ```

### Agent rules

- Flag string concatenation with `+=` inside loops — suggest `strings.Builder`.
- Flag `fmt.Sprintf("%d", n)` / `fmt.Sprintf("%f", f)` — suggest `strconv` alternatives.
- Flag `make([]T, 0)` or `[]T{}` where the length is predictable — suggest `make([]T, 0, len(input))`.

---

## Category 3 — Mutex and Concurrent Access Patterns

### Why it matters

Incorrect mutex usage causes either data races (no mutex where needed) or excessive contention (mutex held too long, or `sync.Mutex` where `sync.RWMutex` would suffice for read-heavy access).

### What to look for

1. **`sync.Mutex` protecting a map that is read frequently but written rarely** — use `sync.RWMutex`:
   ```go
   // BAD: exclusive lock for reads prevents concurrent reads
   var mu sync.Mutex
   var cache map[string]string

   func get(key string) string {
       mu.Lock()
       defer mu.Unlock()
       return cache[key]
   }

   // GOOD: read lock allows concurrent reads
   var mu sync.RWMutex

   func get(key string) string {
       mu.RLock()
       defer mu.RUnlock()
       return cache[key]
   }
   ```

2. **Mutex held during I/O** (DB calls, HTTP requests) — blocks all other goroutines trying to acquire the lock:
   ```go
   // BAD: holds lock while waiting for DB
   mu.Lock()
   defer mu.Unlock()
   result, err := db.Query(ctx, "SELECT * FROM users")
   ```

3. **`sync.Map` used when `map + RWMutex` would be cleaner** — `sync.Map` is optimized for specific access patterns (many goroutines reading different keys) and is harder to reason about.

4. **Data races in counter updates** — `count++` on a shared variable without atomic operations or mutex.

### Agent rules

- Flag `sync.Mutex` on maps that have read operations — suggest `sync.RWMutex`.
- Flag mutex held across database or network I/O calls.
- Flag `count++` / `n += 1` on package-level variables accessed from goroutines — suggest `sync/atomic`.

---

## Category 4 — Interface and Reflection Overhead

### Why it matters

Interface dispatch in Go requires two pointer dereferences (type + value), and values stored in interfaces escape to the heap. In tight loops, this adds up.

### What to look for

1. **Functions that accept `interface{}`** (or `any`) in hot paths when a concrete type would work:
   ```go
   // BAD in hot paths: `v interface{}` boxes the value, causes heap allocation
   func processItem(v interface{}) { ... }

   // GOOD: generic (Go 1.18+) — no boxing
   func processItem[T Processable](v T) { ... }
   ```

2. **`reflect` usage** in hot code paths — reflection is 10–100× slower than direct field access.

3. **JSON marshaling in tight loops** — each `json.Marshal` call uses reflection internally. Pre-generate with `easyjson` or `jsoniter` for hot paths.

### Agent rules

- Flag `interface{}` / `any` parameters in functions called > 100 times (estimate from call sites in hot paths).
- Flag `reflect.ValueOf` / `reflect.TypeOf` inside loop bodies.

---

## Category 5 — HTTP Handler Patterns (Gin / Echo / Chi / Fiber)

### Why it matters

Go HTTP handlers share concerns across all frameworks. The most common issues are reading the entire request body into memory, not reusing HTTP clients, and not setting response headers correctly.

### What to look for

1. **Creating a new `http.Client` per request** — each client creates a new connection pool:
   ```go
   // BAD: new connection pool on every request
   func handler(c *gin.Context) {
       client := &http.Client{Timeout: 5 * time.Second}
       resp, _ := client.Get("https://api.example.com")
   }

   // GOOD: package-level shared client
   var httpClient = &http.Client{Timeout: 5 * time.Second}
   ```

2. **`ioutil.ReadAll(r.Body)` on large request bodies** without size limits — allows clients to exhaust server memory:
   ```go
   // BAD: reads unlimited bytes
   body, _ := ioutil.ReadAll(r.Body)

   // GOOD: limit request body size
   r.Body = http.MaxBytesReader(w, r.Body, 1<<20) // 1MB limit
   body, _ := ioutil.ReadAll(r.Body)
   ```

3. **`gin.Context.JSON` with large slices** — marshals the entire slice before streaming. For large datasets, use streaming JSON.

4. **Missing `defer r.Body.Close()`** — keeps the HTTP connection open.

### Agent rules

- Flag `http.Client{}` instantiation inside handler functions — suggest package-level client.
- Flag `ioutil.ReadAll(r.Body)` without preceding `http.MaxBytesReader`.
- Flag `defer r.Body.Close()` missing on response bodies.

---

## Category 6 — Error Handling

### Why it matters

Go errors are values — they must be checked explicitly. Ignored errors are silent failures that manifest as incorrect behavior or panics later.

### What to look for

1. **`_` used to discard errors from functions that can fail**:
   ```go
   // BAD: silently ignores error
   result, _ := db.Query(ctx, query)

   // GOOD
   result, err := db.Query(ctx, query)
   if err != nil {
       return fmt.Errorf("querying users: %w", err)
   }
   ```

2. **`panic` used for recoverable errors** — should return an error instead.

3. **Error strings starting with a capital letter or ending with punctuation** — Go convention: `errors.New("failed to connect")` not `"Failed to connect."`.

4. **Missing `%w` wrapping** — callers can't use `errors.Is()` to check wrapped error types.

### Agent rules

- Flag `_, _ = someFunc()` patterns where both return values are discarded.
- Flag `if err != nil { return err }` without `fmt.Errorf("%w", err)` wrapping — loses context.

---

## System Prompt

```
Focus areas for Go:
- Goroutine leaks: http.Get/http.Post without context timeout; go func() infinite loops
  without ctx.Done() exit path; context.WithCancel/Timeout without defer cancel().
- Memory allocations: string += in loops (use strings.Builder); fmt.Sprintf for simple
  int/float conversion (use strconv); slices created with []T{} when capacity is known
  (pre-allocate with make([]T, 0, n)); large struct returns by value in hot paths.
- Mutex patterns: sync.Mutex on read-heavy maps (use sync.RWMutex for concurrent reads);
  mutex held across database or network I/O; unsynchronized counter increments.
- Interfaces: interface{}/any parameters in hot paths (use generics in Go 1.18+);
  reflect usage inside loop bodies.
- HTTP handlers: http.Client created per-request (use package-level shared client);
  ioutil.ReadAll without http.MaxBytesReader (unbounded memory); missing defer r.Body.Close().
- Error handling: discarded errors with _; fmt.Errorf without %w (loses error type for
  errors.Is/As); panic for recoverable errors.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Goroutine leak fix | Goroutine count | `runtime.NumGoroutine()` / `pprof` |
| Allocation reduction | Allocations/op, Bytes/op | `go test -bench -benchmem` |
| Mutex contention | Mutex wait time | `pprof mutex` profile |
| HTTP client reuse | TCP connections opened | `net/http` Transport metrics |
| Error propagation | Panic rate | Application logs |
