"""Rust optimization focus areas (Axum, Actix-web, Rocket, Warp, etc.)."""

FOCUS = """
Focus areas for Rust:

-- Existing patterns --
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

-- Rule catalog (apply low-risk first) --

Rule RS-CLONE-001 — Unnecessary .clone() where a borrow suffices
  Anti-pattern : `let x = val.clone(); function_taking_ref(&x)` or `vec.push(s.clone())`
                 where the original value is still needed but only a shared reference
                 is required by the consumer
  Detection    : Rust AST — `.clone()` call whose result is immediately passed to
                 a function expecting `&T`; or `.clone()` inside a loop body on
                 a value that doesn't need ownership
  Patch (low)  : Pass `&val` directly; change function signature to accept `&T`
                 if ownership is not required
  Validate     : `cargo clippy`; unit tests; benchmark allocation count
  Rollback if  : borrow checker rejects due to lifetime conflicts
  Do NOT apply : value must be owned (e.g. moved into a thread, stored in a struct)

Rule RS-MUTEX-AWAIT-002 — Mutex held across an .await point
  Anti-pattern : `let guard = mutex.lock().await; do_work(); other_await().await;`
                 where `guard` is held while awaiting another future — can cause
                 deadlocks and poor async scheduling
  Detection    : Rust AST — `MutexGuard` binding in scope at an `.await` expression
                 (Tokio/futures lint: `clippy::await_holding_lock`)
  Patch (medium): Clone or copy the needed data out of the guard before releasing it;
                 restructure to drop the guard before the await point
  Validate     : `cargo clippy -- -W clippy::await_holding_lock`; deadlock tests
  Rollback if  : restructuring changes observable lock-ordering behaviour
  Do NOT apply : using `parking_lot::Mutex` which is async-aware in some contexts

Rule RS-COLLECT-003 — Collect then immediately iter
  Anti-pattern : `let v: Vec<_> = iter.collect(); v.iter().map(...)` where the
                 intermediate Vec is not needed
  Detection    : Rust AST — `.collect::<Vec<_>>()` call result immediately used
                 in `.iter()` / `.into_iter()` with no other use of the Vec
  Patch (low)  : Remove `.collect()` and chain the next iterator operation directly
  Validate     : `cargo clippy`; unit tests
  Rollback if  : intermediate Vec is needed for random access or multiple passes
  Do NOT apply : collect is required to satisfy a type boundary or trait requirement

Rule RS-SPAWN-BLOCKING-004 — CPU-bound work in async fn without spawn_blocking
  Anti-pattern : CPU-intensive computation (`serde_json::to_string` on large data,
                 compression, image processing, crypto) called directly in an async
                 fn, blocking the Tokio executor thread
  Detection    : Rust AST — call to known CPU-heavy functions inside `async fn` body
                 without `tokio::task::spawn_blocking`
  Patch (medium): Wrap with `tokio::task::spawn_blocking(|| expensive_fn()).await?`
  Validate     : Load test Tokio task metrics; latency p99 under concurrent load
  Rollback if  : function requires access to async resources not available in
                 spawn_blocking closure
  Do NOT apply : function is provably fast (< 1 µs); called only at startup

Rule RS-UNWRAP-005 — .unwrap() in production code path
  Anti-pattern : `.unwrap()` or `.expect("...")` on Result/Option in non-test code
                 that handles user requests or business logic
  Detection    : Rust AST — `.unwrap()` call in a non-test module (not `#[cfg(test)]`);
                 excluding test utilities and well-understood infallible operations
  Patch (medium): Replace with `?` operator; or `unwrap_or`, `unwrap_or_else`,
                 `ok_or` for Option → Result conversion with meaningful error
  Validate     : `cargo clippy -- -W clippy::unwrap_used`; unit tests
  Rollback if  : error type incompatible with calling function's error type
  Do NOT apply : explicitly infallible operation (e.g. locking a non-poisonable mutex
                 in single-threaded context); test code

Rule RS-ENUM-DISPATCH-006 — Box<dyn Trait> for a fixed, closed set of types
  Anti-pattern : `Box<dyn Handler>` or `Arc<dyn Strategy>` when all concrete
                 implementations are known at compile time in the same codebase
  Detection    : Rust AST — `Box<dyn Trait>` or `Arc<dyn Trait>` field/return type
                 where all implementors are defined in the same crate
  Patch (high) : Replace with an enum with variants for each concrete type;
                 implement the trait via a match in a single enum method
  Validate     : Benchmark dynamic dispatch vs enum dispatch in hot path;
                 check binary size reduction
  Rollback if  : trait objects needed for external/plugin extensibility
  Do NOT apply : set of implementations is open or defined externally
"""
