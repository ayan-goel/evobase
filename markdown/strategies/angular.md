# Agent Optimization Strategy — Angular

Angular is a full opinionated framework with a component-based architecture, dependency injection, two-way data binding, and Zone.js for change detection. Its performance model is fundamentally different from React/Vue — it uses Zone.js to intercept async operations and trigger change detection cycles. Most Angular performance issues stem from the default change detection strategy, memory leaks from RxJS subscriptions, and sub-optimal module loading.

---

## Detection

| Signal | Confidence |
|---|---|
| `@angular/core` in deps | 0.95 |
| `angular.json` exists | 0.9 |
| `tsconfig.app.json` + `src/app/app.module.ts` | confirms classic Angular |
| `src/app/app.config.ts` (standalone) | Angular 17+ standalone |

---

## Category 1 — Change Detection Strategy

### Why it matters

Angular's default `ChangeDetectionStrategy.Default` re-checks every component in the tree on any async event (click, HTTP response, timer). A large app with the default strategy runs O(n) checks on every interaction. Switching to `OnPush` reduces this to O(changed components).

### What to look for

1. **Components missing `changeDetection: ChangeDetectionStrategy.OnPush`**:
   ```ts
   // BAD: entire tree re-checks on any event
   @Component({ selector: "app-user-card", template: "..." })
   export class UserCardComponent { ... }

   // GOOD: only re-checks when @Input references change or events fire inside
   @Component({
     selector: "app-user-card",
     template: "...",
     changeDetection: ChangeDetectionStrategy.OnPush,
   })
   export class UserCardComponent { ... }
   ```

2. **Components that mutate `@Input` objects directly** instead of replacing references — this silently breaks `OnPush`:
   ```ts
   // BAD with OnPush: mutates in place, Angular doesn't see a new reference
   this.user.name = "Alice";

   // GOOD: new reference triggers re-check
   this.user = { ...this.user, name: "Alice" };
   ```

3. **`ChangeDetectorRef.detectChanges()` called in a loop** — often a sign that the underlying state management is fighting Angular's CD cycle.

### Agent rules

- Add `changeDetection: ChangeDetectionStrategy.OnPush` to every `@Component` that is missing it.
- Flag direct mutation of `@Input` objects in components that use or should use `OnPush`.

---

## Category 2 — RxJS Subscription Memory Leaks

### Why it matters

Angular components are destroyed when navigated away from. If an RxJS subscription created in the component is not unsubscribed, it keeps the component alive in memory and the callback continues to fire — causing subtle bugs and memory leaks.

### What to look for

1. **`subscribe()` calls without unsubscription** in `ngOnInit` or the constructor:
   ```ts
   // BAD: subscription lives forever after component is destroyed
   ngOnInit() {
     this.userService.getUser().subscribe(user => this.user = user);
   }

   // GOOD: takeUntilDestroyed (Angular 16+)
   private destroyRef = inject(DestroyRef);
   ngOnInit() {
     this.userService.getUser()
       .pipe(takeUntilDestroyed(this.destroyRef))
       .subscribe(user => this.user = user);
   }
   ```

2. **`interval()` or `timer()` observables** without unsubscription.

3. **`fromEvent()` subscriptions** attached to DOM elements or `window` without cleanup.

4. **Multiple subscriptions managed with individual `Subscription` objects** instead of a `Subject` + `takeUntil` or `takeUntilDestroyed`.

### Agent rules

- Add `takeUntilDestroyed(this.destroyRef)` to all subscriptions in components.
- Convert `ngOnDestroy` + manual `subscription.unsubscribe()` patterns to `takeUntilDestroyed` (Angular 16+) or `takeUntil(this.destroy$)` + `Subject` pattern for older Angular.

---

## Category 3 — Impure Pipes and `trackBy`

### Why it matters

- **Impure pipes** run on every change detection cycle (every render). They should be used only when truly necessary.
- **`trackBy`** in `*ngFor` tells Angular how to identify list items, preventing it from destroying and recreating DOM nodes when the array reference changes.

### What to look for

1. **`*ngFor` without `trackBy`**:
   ```html
   <!-- BAD: destroys/recreates all DOM nodes when array reference changes -->
   <div *ngFor="let item of items">{{ item.name }}</div>

   <!-- GOOD -->
   <div *ngFor="let item of items; trackBy: trackById">{{ item.name }}</div>
   ```
   ```ts
   trackById(index: number, item: Item) { return item.id; }
   ```

2. **Custom pipes without `pure: true` (the default)** that perform heavy computations — they'll re-run on every CD cycle.

3. **Methods called in templates** — equivalent to impure pipe problem in React. These run on every CD cycle:
   ```html
   <!-- BAD: formatDate() runs on every change detection cycle -->
   <p>{{ formatDate(user.createdAt) }}</p>

   <!-- GOOD: use a pure pipe -->
   <p>{{ user.createdAt | date:'short' }}</p>
   ```

### Agent rules

- Add `trackBy` to every `*ngFor` that iterates objects with unique IDs.
- Flag template method calls that perform formatting/computation — suggest pipes or pre-computed properties.

---

## Category 4 — Lazy Loading Modules and Routes

### Why it matters

The default Angular build puts everything in a single initial bundle. Lazy loading defers loading of feature modules until they are navigated to, dramatically improving initial load time.

### What to look for

1. **Feature modules imported directly into `AppModule`** instead of lazily loaded:
   ```ts
   // BAD: loads entire AdminModule on app start
   @NgModule({
     imports: [AdminModule, UserModule, ...],
   })
   export class AppModule {}
   ```
   ```ts
   // GOOD: loads AdminModule only when /admin route is accessed
   const routes: Routes = [
     {
       path: "admin",
       loadChildren: () => import("./admin/admin.module").then(m => m.AdminModule),
     },
   ];
   ```

2. **Standalone components not using `loadComponent`** for route-level lazy loading (Angular 17+).

3. **Large third-party libraries** (chart libraries, map libraries) imported in eagerly-loaded modules.

### Agent rules

- Convert feature module imports in `AppModule` to `loadChildren` lazy routes.
- Flag large third-party imports in eagerly-loaded modules — suggest dynamic `import()`.

---

## Category 5 — Zone.js and Async Optimization

### Why it matters

Zone.js intercepts every async operation (setTimeout, Promise, fetch, etc.) to trigger change detection. Code that creates many async operations (e.g. animation loops, WebSocket message handlers) can cause excessive change detection cycles.

### What to look for

1. **`setInterval` or `requestAnimationFrame` in components** that modify data frequently — each tick triggers a full CD cycle:
   ```ts
   // BAD: CD runs every 16ms
   ngOnInit() {
     this.intervalId = setInterval(() => this.counter++, 16);
   }

   // GOOD: run outside zone, only re-enter when done
   constructor(private ngZone: NgZone) {}
   ngOnInit() {
     this.ngZone.runOutsideAngular(() => {
       this.intervalId = setInterval(() => {
         this.counter++;
         if (this.counter % 60 === 0) {
           this.ngZone.run(() => {}); // update UI every 60 frames
         }
       }, 16);
     });
   }
   ```

2. **Third-party library event callbacks** that fire frequently (Leaflet, Chart.js, socket.io) without `runOutsideAngular`.

### Agent rules

- Flag `setInterval` with intervals < 100ms inside components — suggest `ngZone.runOutsideAngular`.
- Flag WebSocket/socket.io event listeners not wrapped in `ngZone.runOutsideAngular`.

---

## Category 6 — Signals (Angular 17+)

### Why it matters

Angular Signals are a new reactive primitive (Angular 17+) that enables fine-grained reactivity without Zone.js overhead. They allow `OnPush` components to be even more efficient.

### What to look for

1. **BehaviorSubject patterns** in services that could be replaced with `signal()`:
   ```ts
   // BAD: requires subscribe/unsubscribe management
   private userSubject = new BehaviorSubject<User | null>(null);
   user$ = this.userSubject.asObservable();

   // GOOD: reactive, no subscription needed in template
   user = signal<User | null>(null);
   ```

2. **`computed()` available** for derived signals instead of `pipe(map(...))` observable chains.

3. **`effect()` for side effects** triggered by signal changes instead of `tap()` in observable chains.

### Agent rules

- Suggest replacing `BehaviorSubject` + `async` pipe patterns with `signal()` in Angular 17+ projects.
- Flag observable chains used solely for derivation where `computed()` would be simpler.

---

## System Prompt

```
Focus areas for Angular:
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
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| OnPush adoption | CD cycle count | Angular DevTools Profiler |
| Subscription leak fix | Memory usage (MB) | Chrome Memory tab |
| trackBy | List re-render time | Angular DevTools |
| Lazy loading | Initial bundle size | Angular build output |
| runOutsideAngular | CD invocations/second | Angular DevTools |
