# Agent Optimization Strategy — Rust

Rust's ownership and borrow checker eliminate entire classes of bugs (use-after-free, data races, null pointer dereferences) at compile time. This means the agent can focus on a higher tier of concerns: unnecessary heap allocations, cloning when borrowing would suffice, `Arc<Mutex<T>>` contention, async executor patterns, and iterator efficiency. Correctness issues in Rust are almost always caught at compile time — but performance issues are not.

---

## Detection

| Signal | Confidence |
|---|---|
| `Cargo.toml` exists | 0.9 |
| `Cargo.lock` exists | +0.05 |
| `axum` in `[dependencies]` | framework = `axum` |
| `actix-web` in `[dependencies]` | framework = `actix` |
| `rocket` in `[dependencies]` | framework = `rocket` |
| `warp` in `[dependencies]` | framework = `warp` |

Default commands:
- Install: `cargo fetch`
- Build: `cargo build --release`
- Test: `cargo test`
- Typecheck: `cargo check`
- Lint: `cargo clippy -- -D warnings`
- Bench: `cargo bench`

---

## Category 1 — Unnecessary Clones

### Why it matters

`.clone()` creates a deep copy on the heap. In tight loops or hot paths this adds significant allocation pressure and GC-like pauses from the allocator. Rust's borrow checker forces developers to add `.clone()` when the lifetime analysis can't prove safety — but many clones are avoidable with better lifetime annotations or restructured code.

### What to look for

1. **Cloning a string/Vec just to pass it to a function** when a borrow would work:
   ```rust
   // BAD: clones the entire String
   let name = user.name.clone();
   println!("{}", process_name(name));

   // GOOD: borrow
   println!("{}", process_name(&user.name));
   ```

2. **`.to_string()` / `.to_owned()` on string literals** when `&str` would suffice:
   ```rust
   // BAD: allocates a String
   fn get_label() -> String {
       "active".to_string()
   }

   // GOOD: returns a borrowed str
   fn get_label() -> &'static str {
       "active"
   }
   ```

3. **Cloning inside a loop** — each iteration allocates:
   ```rust
   // BAD: clones config on every iteration
   for item in &items {
       process(item, config.clone());
   }

   // GOOD: pass a reference
   for item in &items {
       process(item, &config);
   }
   ```

4. **`Arc::clone()` inside a loop** to share ownership — consider restructuring to pass a single reference to the task instead of cloning the Arc per iteration.

### Agent rules

- Flag `.clone()` calls where the value is immediately passed to a function — check if the function can accept a reference.
- Flag `.to_string()` / `.to_owned()` on string literals where the caller could accept `&str`.
- Flag `.clone()` inside `for` loop bodies.

---

## Category 2 — `Arc<Mutex<T>>` Contention

### Why it matters

`Arc<Mutex<T>>` is the standard way to share mutable state across threads in Rust. But holding the lock for too long, or locking too frequently, causes thread contention. Prefer `Arc<RwLock<T>>` for read-heavy data, and prefer message passing (channels) for coordination over shared state.

### What to look for

1. **`Mutex` held across `await` points** in async code — causes the lock to be held while the task is suspended (other tasks can't proceed):
   ```rust
   // BAD: lock held during await
   let guard = mutex.lock().await;
   let result = expensive_async_operation().await; // lock held here!
   drop(guard);

   // GOOD: drop the lock before awaiting
   let data = {
       let guard = mutex.lock().await;
       guard.clone() // take what you need
   };
   let result = expensive_async_operation_with(data).await;
   ```

2. **`Mutex<HashMap<K, V>>`** for read-heavy access — prefer `RwLock<HashMap<K, V>>`:
   ```rust
   // BAD: exclusive lock prevents concurrent reads
   static CACHE: Mutex<HashMap<String, Value>> = Mutex::new(HashMap::new());

   // GOOD: read lock allows concurrent readers
   static CACHE: RwLock<HashMap<String, Value>> = RwLock::new(HashMap::new());
   ```

3. **Locking on every request** in a web handler — consider `DashMap` for fine-grained concurrent maps, or `tokio::sync::OnceCell` for one-time initialization.

### Agent rules

- Flag `mutex.lock()` followed by `.await` while the guard is still in scope.
- Flag `Mutex<HashMap<...>>` — suggest `RwLock` if reads outnumber writes.

---

## Category 3 — Allocation Reduction

### Why it matters

Rust doesn't have a GC, but the heap allocator still has overhead. Each `Box`, `Vec`, `String`, `Rc`, `Arc` allocation is a syscall-like operation. In a high-throughput server, reducing allocations per request directly improves throughput.

### What to look for

1. **Collecting into a `Vec` only to iterate once** — use iterators directly:
   ```rust
   // BAD: allocates a Vec just to sum it
   let items: Vec<i64> = records.iter().map(|r| r.value).collect();
   let total: i64 = items.iter().sum();

   // GOOD: no intermediate allocation
   let total: i64 = records.iter().map(|r| r.value).sum();
   ```

2. **`format!` in hot paths for string construction** — use `write!` into a pre-allocated buffer:
   ```rust
   // BAD: allocates a new String each time
   let msg = format!("Error at line {}: {}", line, message);

   // GOOD for very hot paths: write into existing buffer
   let mut buf = String::with_capacity(64);
   write!(&mut buf, "Error at line {}: {}", line, message)?;
   ```

3. **`Box<dyn Trait>` in hot paths** — dynamic dispatch + heap allocation. For a fixed set of types, use an enum instead:
   ```rust
   // BAD: heap alloc + vtable dispatch
   let handler: Box<dyn Handler> = match kind {
       "a" => Box::new(HandlerA),
       "b" => Box::new(HandlerB),
   };

   // GOOD: enum dispatch, no heap allocation
   enum AnyHandler { A(HandlerA), B(HandlerB) }
   impl AnyHandler {
       fn handle(&self) { match self { Self::A(h) => h.handle(), Self::B(h) => h.handle() } }
   }
   ```

### Agent rules

- Flag `.collect::<Vec<_>>()` followed immediately by `.iter()` — can be removed.
- Flag `format!()` in functions called in loops or hot paths — suggest `write!` + pre-allocated buffer.
- Flag `Box<dyn Trait>` in functions that handle a fixed, closed set of types — suggest enum.

---

## Category 4 — Async Executor Patterns (Tokio)

### Why it matters

Tokio is Rust's dominant async runtime. Incorrect use of its APIs — spawning too many tasks, blocking in async tasks, missing `JoinSet` for structured concurrency — leads to performance problems and resource leaks.

### What to look for

1. **Blocking operations inside `async fn`** — Tokio's async tasks run on a thread pool. A blocking call stalls the thread, preventing other tasks from running:
   ```rust
   // BAD: std::thread::sleep blocks the Tokio thread
   async fn handler() {
       std::thread::sleep(Duration::from_secs(1));
   }

   // GOOD: yield to the runtime
   async fn handler() {
       tokio::time::sleep(Duration::from_secs(1)).await;
   }
   ```

2. **CPU-bound work in async tasks** — use `tokio::task::spawn_blocking` to run on a dedicated blocking thread:
   ```rust
   // BAD: heavy computation on Tokio worker thread
   async fn compress(data: Vec<u8>) -> Vec<u8> {
       do_heavy_cpu_compression(&data) // starves other tasks
   }

   // GOOD
   async fn compress(data: Vec<u8>) -> Vec<u8> {
       tokio::task::spawn_blocking(move || do_heavy_cpu_compression(&data))
           .await
           .unwrap()
   }
   ```

3. **`tokio::spawn` without tracking the `JoinHandle`** — if the task panics, it's silently dropped. Fire-and-forget spawns should at least log panics.

4. **Awaiting all futures sequentially** with `.await` in a loop when they could run concurrently:
   ```rust
   // BAD: sequential
   for id in &ids {
       let result = fetch(id).await?;
       results.push(result);
   }

   // GOOD: concurrent with JoinSet
   let mut set = JoinSet::new();
   for id in &ids {
       set.spawn(fetch(*id));
   }
   while let Some(result) = set.join_next().await {
       results.push(result??);
   }
   ```

### Agent rules

- Flag `std::thread::sleep` inside `async fn` — suggest `tokio::time::sleep`.
- Flag CPU-bound function calls in `async fn` — suggest `tokio::task::spawn_blocking`.
- Flag sequential `.await` loops over independent futures — suggest `JoinSet` or `futures::join_all`.

---

## Category 5 — Iterator Efficiency

### Why it matters

Rust's iterators are zero-cost abstractions — they compile to the same code as hand-written loops. Using the right iterator adapters avoids redundant passes, allocations, and branches.

### What to look for

1. **`.filter().map()` instead of `.filter_map()`**:
   ```rust
   // BAD: two passes conceptually
   items.iter().filter(|x| x.is_some()).map(|x| x.unwrap())

   // GOOD
   items.iter().filter_map(|x| *x)
   ```

2. **`.iter().position()` to check existence** instead of `.iter().any()`:
   ```rust
   // BAD: returns index, but only existence is needed
   if items.iter().position(|x| x == &target).is_some() { ... }

   // GOOD: short-circuits
   if items.iter().any(|x| x == &target) { ... }
   ```

3. **`.collect()` + `.iter()` chains** instead of lazy iteration (see Category 3).

4. **`Vec::contains` in hot paths on large vecs** — O(n) linear scan. Use a `HashSet` for O(1) membership:
   ```rust
   // BAD: O(n) per check
   if valid_ids.contains(&id) { ... }

   // GOOD: O(1) average
   if valid_ids_set.contains(&id) { ... }
   ```

### Agent rules

- Flag `.filter(...).map(...)` chains that unwrap Options — suggest `.filter_map()`.
- Flag `Vec::contains` on collections where the check is inside a loop — suggest `HashSet`.

---

## Category 6 — Error Handling with `?` Operator

### Why it matters

The `?` operator is idiomatic Rust. Missing it leads to verbose match/unwrap patterns, and `unwrap()` / `expect()` in non-test production code can panic.

### What to look for

1. **`unwrap()` in production code paths** (non-test, non-prototype) — panics if the value is `None` or `Err`:
   ```rust
   // BAD: panics if db returns an error
   let user = db.get_user(id).unwrap();

   // GOOD: propagate the error
   let user = db.get_user(id)?;
   ```

2. **Manual `match` on `Result` when `?` or `map_err` would be cleaner**:
   ```rust
   // BAD: verbose
   let data = match read_file(path) {
       Ok(d) => d,
       Err(e) => return Err(e),
   };

   // GOOD
   let data = read_file(path)?;
   ```

3. **`expect("message")` in library code** — libraries should return errors, not panic.

### Agent rules

- Flag `.unwrap()` in non-test code files (exclude `#[cfg(test)]` blocks and `_test.rs` files).
- Flag `match result { Ok(v) => v, Err(e) => return Err(e) }` — suggest `?`.

---

## System Prompt

```
Focus areas for Rust:
- Unnecessary clones: .clone() where a borrow (&T) would suffice; .to_string()/.to_owned()
  on string literals when &str is possible; .clone() inside for loops.
- Arc<Mutex<T>> contention: Mutex held across .await points; Mutex<HashMap> for read-heavy
  access (use RwLock); DashMap for concurrent insert/read patterns.
- Allocations: .collect::<Vec<_>>() immediately followed by .iter() (remove the collect);
  format!() in hot paths (use write! into pre-allocated buffer); Box<dyn Trait> for fixed
  closed type sets (use enum dispatch).
- Tokio async: std::thread::sleep in async fn (use tokio::time::sleep); CPU-bound work
  in async fn (use spawn_blocking); sequential .await in loop over independent futures
  (use JoinSet or join_all).
- Iterators: .filter(...).map(Option::unwrap) chains (use filter_map); Vec::contains in
  loops over large collections (use HashSet).
- Error handling: .unwrap() in non-test production code (propagate with ?); manual match
  on Result returning Err (use ?).
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| Clone reduction | Allocations/op | `cargo bench` + `criterion` |
| Mutex → RwLock | Lock contention time | `tokio-console` / `perf` |
| spawn_blocking | Async task latency (µs) | `tokio-console` |
| JoinSet parallelism | Total operation time (ms) | `criterion` / wall clock |
| HashSet vs Vec::contains | Lookup time (ns) | `cargo bench` |
