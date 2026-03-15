"""Generic JVM (Java / Kotlin / Quarkus / Micronaut) optimization focus areas."""

FOCUS = """
Focus areas for JVM (Java/Kotlin):

-- Existing patterns --
- Object allocation in hot paths: boxing primitives (Integer, Long) in tight loops;
  StringBuilder misuse (string concatenation with + in loops); redundant .toString()
  on already-String values.
- Collections: ArrayList.contains() on large lists (use HashSet); HashMap with poor
  hashCode implementations causing bucket collisions; ConcurrentHashMap vs synchronized
  HashMap for concurrent access.
- I/O: blocking I/O on virtual threads or reactive pipelines; missing buffering on
  FileInputStream/FileOutputStream; reading entire files into memory instead of streaming.
- Null safety: Optional misuse — Optional.get() without isPresent() check; using Optional
  as method parameter type (use @Nullable instead).
- Resource leaks: try-with-resources missing on Closeable resources (streams, connections,
  readers); JDBC Connection/PreparedStatement not closed.
- Kotlin-specific: using Java stream APIs instead of Kotlin collection extensions;
  data class copy() in hot paths creating excessive allocations.

-- Rule catalog (apply low-risk first) --

Rule JVM-PRIM-001 — Unnecessary primitive boxing in hot paths
  Anti-pattern : `Integer count = 0; count++` or `Long total = values.stream().mapToLong(...).sum()`
                 — boxing allocates heap objects on every assignment in a tight loop
  Detection    : Java/Kotlin AST — `Integer`/`Long`/`Double`/`Boolean` local variable
                 inside a for/while loop body; or `Stream<Integer>` where
                 `IntStream`/`LongStream` would eliminate boxing
  Patch (low/medium): Use primitive local variables (`int`, `long`);
                 replace `Stream<Integer>` with `IntStream`;
                 use `LongAdder` or `AtomicLong` for thread-safe counters
  Validate     : JMH benchmark allocation rate before/after; GC pause metrics
  Rollback if  : generic API requires boxed type; not in a measured hot path
  Do NOT apply : single-use variable not in a loop; boxing overhead negligible

Rule JVM-STR-002 — String concatenation with + in a loop
  Anti-pattern : `String result = ""; for (item in list) { result += item; }`
                 — creates a new String object on every iteration (O(n²) allocations)
  Detection    : Java/Kotlin AST — `+=` on a String variable inside a loop body
  Patch (low)  : Replace with `StringBuilder sb = new StringBuilder(); sb.append(item); sb.toString()`
                 or Kotlin: `buildString { list.forEach { append(it) } }`
  Validate     : JMH benchmark; heap allocation profiler
  Rollback if  : trivially short loop (< 5 items) — micro-optimisation not worth it
  Do NOT apply : loop is not on a hot path; fewer than 5 concatenations

Rule JVM-CONTAINS-003 — ArrayList.contains() in a loop
  Anti-pattern : `if (list.contains(item))` inside a loop where `list` has > ~100
                 elements — O(n) per call, O(n²) overall
  Detection    : Java/Kotlin AST — `.contains(` call on a variable of type `List`/
                 `ArrayList` inside a loop body; list size not obviously bounded small
  Patch (low/medium): Convert to `Set<T> set = new HashSet<>(list)` outside the loop;
                 use `set.contains(item)` — O(1) lookup
  Validate     : Benchmark with realistic collection sizes
  Rollback if  : list preserves insertion order intentionally; set semantics differ
  Do NOT apply : list is known to be very small (< 10 elements consistently)

Rule JVM-RESOURCE-004 — Closeable resource not in try-with-resources
  Anti-pattern : `FileInputStream fis = new FileInputStream(path); ... fis.close()`
                 in a finally block, or missing close() entirely — leaks file descriptors
                 on exceptions
  Detection    : Java AST — `InputStream`/`OutputStream`/`Connection`/`Statement`
                 variable assignment not inside a `try (...)` resource declaration;
                 or close() called in a finally block without a wrapping try-with-resources
  Patch (low)  : Refactor to `try (var fis = new FileInputStream(path)) { ... }`
  Validate     : `close()` called on exception path; `javac -Xlint:try` warnings
  Rollback if  : resource lifetime must extend beyond the current try block
  Do NOT apply : resource is managed by a framework (Spring @Bean lifecycle)

Rule JVM-OPTIONAL-005 — Optional.get() without isPresent() check
  Anti-pattern : `optional.get()` called directly without guarding with
                 `optional.isPresent()` or using `optional.orElse(...)` —
                 throws NoSuchElementException at runtime
  Detection    : Java/Kotlin AST — `.get()` call on an `Optional`-typed variable
                 not preceded by `.isPresent()` check in the same scope
  Patch (low)  : Replace `opt.get()` with `opt.orElseThrow()` for explicit failure,
                 or `opt.orElse(default)` / `opt.ifPresent(consumer)` for safe access
  Validate     : Unit test with empty Optional; `SpotBugs` / `NullAway` static check
  Rollback if  : semantics of orElseThrow differ from caller's error handling
  Do NOT apply : `.isPresent()` check is present immediately before `.get()`

Rule JVM-STREAM-006 — Kotlin code using verbose Java Stream API
  Anti-pattern : Kotlin code using `.stream().filter(...).collect(Collectors.toList())`
                 instead of Kotlin's built-in extension functions
  Detection    : Kotlin AST — `.stream()` call on a Collection in a .kt file
  Patch (low)  : Replace with Kotlin idiom: `.filter { ... }.toList()`; use
                 `.asSequence()` for lazy evaluation of multi-step pipelines
  Validate     : Unit tests; `ktlint` or `detekt` warnings
  Rollback if  : Java interop requires a Java Stream (e.g. passing to Java API)
  Do NOT apply : code is Java, not Kotlin; or result must be a Java Stream
"""
