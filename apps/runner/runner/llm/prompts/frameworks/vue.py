"""Vue.js / Nuxt optimization focus areas."""

FOCUS = """
Focus areas for Vue.js / Nuxt:

-- Existing patterns --
- Reactivity misuse: reactive() wrapping primitives (use ref() instead); watchEffect that
  assigns derived values to a ref (should be computed); watch/watchEffect with missing
  flush options causing synchronous watchers in hot paths.
- v-if vs v-show: v-if on elements that toggle frequently (use v-show); v-show on
  conditionally-rendered sections that are rarely shown (use v-if for lazy mounting).
- List rendering: v-for with :key="index" when items have stable IDs; v-for + v-if on
  the same element (extract filter into computed property).
- computed vs methods: methods called in templates that derive data from reactive state
  (convert to computed properties for caching).
- Component lazy loading: heavy components imported synchronously when conditionally
  shown (use defineAsyncComponent); Nuxt: heavy page sections not wrapped in <ClientOnly>
  or using <Lazy> prefix.
- Pinia: store destructuring without storeToRefs (breaks reactivity); getters implemented
  as methods instead of computed properties.

-- Rule catalog (apply low-risk first) --

Rule VUE-COMP-001 — Methods used in template for derived values
  Anti-pattern : template calls like `{{ computeTotal() }}` or `:value="formatDate(item)"`
                 where the method derives data from reactive state and is called
                 on every render cycle
  Detection    : template AST — method call expression (not event handler) in template
                 interpolation or binding; same method defined in `methods:` or as
                 a plain function in setup() without `computed`
  Patch (low/medium): Convert to `computed(() => ...)` in <script setup> or
                 `computed:` in Options API
  Validate     : Unit tests + render profiling (Vue DevTools)
  Rollback if  : behaviour diverges (method had side effects)
  Do NOT apply : method has observable side effects beyond returning a value

Rule VUE-KEEP-002 — Expensive component re-created on every view switch
  Anti-pattern : `<component :is="currentView">` or `v-if` toggling a heavy component
                 that is frequently switched in and out
  Detection    : template — `<component :is=` or multiple `v-if` blocks on sibling
                 components without `<KeepAlive>`; component render time > 100 ms
                 visible in Vue DevTools
  Patch (medium): Wrap with `<KeepAlive :include="['ComponentName']">`; add
                 `onActivated`/`onDeactivated` hooks for data refresh
  Validate     : Navigation interaction tests; confirm state preservation
  Rollback if  : stale state shown; memory footprint increases unacceptably
  Do NOT apply : component data must refresh on every mount (e.g. real-time feed)

Rule VUE-LIST-003 — Missing or unstable :key in v-for
  Anti-pattern : `v-for="item in items"` without `:key`, or `:key="index"`
                 when items have stable unique identifiers
  Detection    : template AST — `v-for` directive without `:key` attribute, or
                 `:key` value is the loop index variable
  Patch (medium): Add `:key="item.id"` using the item's stable unique field
  Validate     : List reorder and mutation tests
  Rollback if  : UI state bugs (focus, animation, form fields)
  Do NOT apply : items have no stable identity (purely positional rendering)

Rule VUE-REACTIVE-004 — reactive() wrapping a primitive value
  Anti-pattern : `const state = reactive(0)` or `reactive('string')` — reactive()
                 on primitives loses reactivity tracking
  Detection    : AST — `reactive(` call with a non-object literal argument
  Patch (low)  : Replace with `ref(value)`; update access to `.value`
  Validate     : Unit tests confirming reactivity is preserved
  Rollback if  : reactivity loss in consuming components
  Do NOT apply : N/A (this is always wrong)

Rule VUE-WATCH-005 — watchEffect assigning derived value to a ref
  Anti-pattern : `watchEffect(() => { derivedRef.value = f(source.value) })`
                 where f is a pure function of reactive sources
  Detection    : AST — watchEffect callback body contains only a ref assignment
                 whose RHS is a pure expression of reactive values
  Patch (low)  : Replace watchEffect with `const derived = computed(() => f(source.value))`
  Validate     : Unit tests
  Rollback if  : side effects were intended inside the watchEffect
  Do NOT apply : watchEffect body has side effects beyond the assignment
"""
