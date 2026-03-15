"""Angular optimization focus areas."""

FOCUS = """
Focus areas for Angular:

-- Existing patterns --
- Change detection: components without ChangeDetectionStrategy.OnPush; direct mutation
  of @Input objects in OnPush components (breaks dirty-checking).
- RxJS memory leaks: subscribe() calls in ngOnInit/constructor without
  takeUntilDestroyed(destroyRef) or takeUntil(destroy$); interval/timer/fromEvent
  observables without cleanup in ngOnDestroy.
- *ngFor: missing trackBy functions; large lists without trackBy cause full DOM
  replacement when the array reference changes.
- Template methods: methods called in templates that perform computation (run every CD
  cycle); convert to pure pipes or pre-computed properties.
- Lazy loading: feature modules imported eagerly in AppModule instead of loadChildren;
  large third-party imports in eagerly-loaded modules.
- Zone.js: setInterval/requestAnimationFrame with high frequency inside components
  without ngZone.runOutsideAngular; socket/WebSocket callbacks not wrapped.
- Signals (Angular 17+): BehaviorSubject patterns that could use signal(); observable
  derivation chains that could use computed().

-- Rule catalog (apply low-risk first) --

Rule NG-ONPUSH-001 — Default change detection on pure-ish components
  Anti-pattern : `@Component({ ... })` without `changeDetection` field, or
                 `changeDetection: ChangeDetectionStrategy.Default` on a component
                 that only reads from @Input and services (no direct DOM mutation)
  Detection    : TS AST — @Component decorator object without `changeDetection`
                 property; component class does not call this.someInputProp = ...
  Patch (medium): Add `changeDetection: ChangeDetectionStrategy.OnPush` to the
                 decorator; ensure all inputs are treated as immutable
  Validate     : Angular DevTools Profiler change-detection cycle count; e2e
  Rollback if  : stale UI; component mutates @Input values in place
  Do NOT apply : component relies on reference mutation of inputs;
                 impure pipes or direct DOM manipulation present

Rule NG-ZONE-002 — High-frequency timers / callbacks inside Zone.js
  Anti-pattern : `setInterval`, `setTimeout`, `requestAnimationFrame`, or
                 WebSocket message handlers inside component/service constructors
                 or ngOnInit without ngZone.runOutsideAngular
  Detection    : TS AST — `setInterval(` or `setTimeout(` call inside a class
                 that is @Component or @Injectable, not wrapped in runOutsideAngular
  Patch (medium): Wrap in `this.ngZone.runOutsideAngular(() => { ... })`; re-enter
                 zone only when a state update is needed via `this.ngZone.run()`
  Validate     : Angular DevTools Profiler; e2e smoke
  Rollback if  : UI not updating correctly after moving outside zone
  Do NOT apply : timer directly drives visible UI on every tick

Rule NG-FOR-003 — Missing trackBy in *ngFor / @for track $index
  Anti-pattern : `*ngFor="let item of items"` without `trackBy`; or
                 `@for (item of items; track $index)` using index as key
  Detection    : template regex — `[*]ngFor=` without `trackBy:` in the same
                 binding; or `@for (... track $index` pattern
  Patch (low/medium): Add `trackBy: trackById` method returning `item.id`; or
                 change `@for` to `track item.id`
  Validate     : List mutation tests; Angular DevTools DOM-diff count
  Rollback if  : wrong row reuse or key collisions
  Do NOT apply : items have no stable identity

Rule NG-DEFER-004 — Heavy below-the-fold content loaded eagerly
  Anti-pattern : Large component subtrees below the visible fold imported and
                 rendered immediately without defer hints
  Detection    : template — component selector below a known scroll boundary
                 without `@defer` or `*ngIf` tied to viewport intersection
  Patch (medium): Wrap with `@defer (on viewport) { <HeavyComponent /> }` with
                 a lightweight `@placeholder`
  Validate     : Lighthouse CI (LCP, CLS guardrails) + e2e
  Rollback if  : CLS regression; above-the-fold content accidentally deferred
  Do NOT apply : content is above the fold; layout is sensitive to placeholder size

Rule NG-AOT-005 — Non-production build in CI
  Anti-pattern : CI runs `ng build` without `--configuration production` or
                 without AOT enabled
  Detection    : file — package.json build script or CI yaml calls `ng build`
                 without `--configuration production` or `--aot`
  Patch (medium): Enforce `ng build --configuration production`
  Validate     : `ng build --configuration production` succeeds; bundle size diff
  Rollback if  : build errors requiring debug tooling
  Do NOT apply : repo intentionally keeps dev build for profiling metadata

Rule NG-SEC-006 — Unsafe HTML bypass / DomSanitizer misuse
  Anti-pattern : `bypassSecurityTrustHtml(...)`, `bypassSecurityTrustScript(...)`,
                 or `[innerHTML]` bindings with user-controlled content
  Detection    : TS AST — calls to `bypassSecurityTrust*` methods; `[innerHTML]`
                 binding with a non-constant expression
  Patch (high) : Advisory only — add security audit comment and tests; do not
                 auto-patch as the correct fix depends on content source
  Validate     : Security-focused e2e tests
  Rollback if  : rendering breaks for legitimate HTML content
  Do NOT apply : always flag for manual review; never silently change sanitizer calls
"""
