# Agent Optimization Strategy — NestJS

NestJS is an opinionated Node.js framework built on top of Express (or Fastify) with TypeScript-first dependency injection, a module system, decorators, and deep integration with TypeORM/Prisma, GraphQL, and microservices. Its structured architecture introduces specific failure patterns around DI misuse, interceptor chains, and N+1 query traps.

---

## Detection

| Signal | Confidence |
|---|---|
| `@nestjs/core` in deps | 0.95 |
| `nest-cli.json` or `@nestjs/cli` in devDeps | 0.9 |
| `src/main.ts` with `NestFactory.create` | confirms NestJS |

---

## Category 1 — Dependency Injection Anti-patterns

### Why it matters

NestJS's DI container manages the lifecycle of services. Bypassing DI by instantiating services with `new` loses singleton management, circular dependency detection, and testability.

### What to look for

1. **Services instantiated with `new` inside other services or controllers**:
   ```ts
   // BAD: bypasses DI, creates a new instance each time
   @Controller("users")
   export class UserController {
     private emailService = new EmailService(); // WRONG

     @Post()
     async create(@Body() dto: CreateUserDto) {
       await this.emailService.sendWelcome(dto.email);
     }
   }

   // GOOD: injected by NestJS
   @Controller("users")
   export class UserController {
     constructor(private readonly emailService: EmailService) {}
   }
   ```

2. **Circular dependencies** not resolved with `forwardRef()` — NestJS throws a runtime error but the cause can be hard to track. The agent should flag potential cycles.

3. **Services that import the entire module** instead of just what they need (overly broad module imports).

### Agent rules

- Flag `new SomeService()` or `new SomeRepository()` inside classes decorated with `@Injectable`, `@Controller`, or `@Module`.
- Flag `@Module` imports arrays that include modules not actually used by the module's exported providers.

---

## Category 2 — N+1 Queries in Service Methods

### Why it matters

A loop that calls a database query per iteration is an N+1 problem — 1 query to get N IDs, then N queries to hydrate each one. This scales catastrophically: 100 users = 101 queries.

### What to look for

**TypeORM pattern:**
```ts
// BAD: N+1 — one findOne per post
async getPostsWithAuthors(postIds: number[]) {
  const posts = await this.postRepo.find({ where: { id: In(postIds) } });
  for (const post of posts) {
    post.author = await this.userRepo.findOne({ where: { id: post.authorId } });
  }
  return posts;
}

// GOOD: single query with join
async getPostsWithAuthors(postIds: number[]) {
  return this.postRepo.find({
    where: { id: In(postIds) },
    relations: ["author"],
  });
}
```

**Prisma pattern:**
```ts
// BAD: N+1
const posts = await prisma.post.findMany();
for (const post of posts) {
  post.author = await prisma.user.findUnique({ where: { id: post.authorId } });
}

// GOOD: include in query
const posts = await prisma.post.findMany({ include: { author: true } });
```

### Agent rules

- Flag `findOne` / `findUnique` / `findById` calls inside loops (for, forEach, map, reduce).
- Suggest `relations: [...]` (TypeORM) or `include: { ... }` (Prisma) to batch the lookup.

---

## Category 3 — Interceptor and Guard Chain Inefficiency

### Why it matters

NestJS interceptors and guards run on every matching request. Duplicate work across them (e.g. fetching the current user in both a guard and an interceptor) wastes database calls.

### What to look for

1. **Database lookups duplicated in guards and interceptors**:
   ```ts
   // BAD: AuthGuard fetches user, then CurrentUserInterceptor fetches user again
   @Injectable()
   export class AuthGuard implements CanActivate {
     async canActivate(ctx: ExecutionContext) {
       const user = await this.usersService.findById(userId); // fetches user
       return !!user;
     }
   }

   @Injectable()
   export class CurrentUserInterceptor implements NestInterceptor {
     async intercept(ctx: ExecutionContext, next: CallHandler) {
       const user = await this.usersService.findById(userId); // fetches AGAIN
       request.user = user;
       return next.handle();
     }
   }

   // GOOD: fetch in guard, attach to request, interceptor reads from request
   ```

2. **Global interceptors doing heavy work** (logging full request/response bodies) that should be sampled or rate-limited.

3. **Guards that perform the same check** as a decorator applied to the handler (e.g. role check in both a global guard and a `@Roles()` decorator handler).

### Agent rules

- Flag services called in multiple guards/interceptors in the same request lifecycle.
- Suggest storing computed values on the `request` object and reading from it in subsequent interceptors.

---

## Category 4 — Missing DTOs and Validation

### Why it matters

Without DTOs and `class-validator`, invalid input reaches business logic. Beyond correctness, missing `@Exclude()` on sensitive fields can expose data in responses.

### What to look for

1. **Route handlers that accept `@Body() body: any`** or untyped objects:
   ```ts
   // BAD: any input accepted
   @Post()
   async create(@Body() body: any) { ... }

   // GOOD: typed DTO with validation
   @Post()
   async create(@Body() dto: CreateUserDto) { ... }
   ```

2. **DTOs without `class-validator` decorators** — if `ValidationPipe` is global, missing decorators mean no validation.

3. **Response serialization without `@Exclude()`** on sensitive fields (passwords, tokens, internal IDs):
   ```ts
   // BAD: password hash returned in API response
   @Get(":id")
   getUser(@Param("id") id: string) {
     return this.usersService.findById(id); // returns User entity with passwordHash
   }

   // GOOD: use a response DTO or @Exclude() on the entity
   @Exclude()
   passwordHash: string;
   ```

### Agent rules

- Flag `@Body() body: any` — suggest creating a typed DTO.
- Flag entity fields that contain sensitive data (passwords, secrets, tokens) without `@Exclude()`.

---

## Category 5 — Heavy Synchronous Work in Request Handlers

### Why it matters

NestJS runs on Node.js — the same event loop concerns apply. CPU-intensive work (image processing, PDF generation, large data transformation) should be offloaded to a queue.

### What to look for

1. **`sharp()`, `pdfkit`, `csv-parse` large file processing** inside request handlers synchronously.

2. **Loops processing thousands of records** in a service method called from a controller — this blocks the event loop for the entire duration.

3. **Missing `@nestjs/bull` (BullMQ) or `@nestjs/schedule`** for operations that don't need to block the request:
   ```ts
   // BAD: blocks response until email is sent
   @Post("/signup")
   async signup(@Body() dto: SignupDto) {
     const user = await this.usersService.create(dto);
     await this.emailService.sendWelcome(user.email); // synchronous wait
     return user;
   }

   // GOOD: queue the email, respond immediately
   @Post("/signup")
   async signup(@Body() dto: SignupDto) {
     const user = await this.usersService.create(dto);
     await this.emailQueue.add("welcome", { email: user.email });
     return user;
   }
   ```

### Agent rules

- Flag `await` calls to email/SMS/push notification services in request handlers — suggest queueing.
- Flag large in-memory data transformations (>1000 items) in synchronous service methods.

---

## Category 6 — Memory Leaks from Event Listeners

### Why it matters

NestJS services are singletons that live for the application lifetime. Event listeners added in service constructors without cleanup accumulate over the application lifetime.

### What to look for

1. **`EventEmitter2` or Node's `EventEmitter` `.on()` in constructors or `onModuleInit`** without `.off()` in `onModuleDestroy`.

2. **RxJS subscriptions in services** without unsubscription on module destroy.

3. **`setInterval` or `setTimeout` in services** without clearing on `onModuleDestroy`.

### Agent rules

- Flag `.on()` event listener registration without corresponding `.off()` / `.removeListener()`.
- Flag `setInterval` in service constructors or lifecycle hooks without `clearInterval` in `onModuleDestroy`.

---

## System Prompt

```
Focus areas for NestJS:
- DI anti-patterns: services instantiated with `new` inside controllers or other services
  (bypasses DI lifecycle and testability); unused module imports in @Module.imports array.
- N+1 queries: findOne/findUnique/findById called inside loops over a collection;
  missing relations: [...] in TypeORM or include: {...} in Prisma to batch hydration.
- Interceptor/guard chains: same database lookup duplicated across a guard and an
  interceptor in the same request pipeline; use request object to share computed values.
- DTOs and validation: @Body() typed as `any`; DTO classes without class-validator
  decorators when ValidationPipe is global; entity fields with sensitive data (passwords,
  tokens) without @Exclude().
- Queue offloading: await calls to email/SMS/push services in request handlers that block
  the response (suggest BullMQ queue); large in-memory loops in synchronous service methods.
- Memory leaks: EventEmitter.on() in constructors/onModuleInit without cleanup in
  onModuleDestroy; setInterval without clearInterval.
```

---

## Measurability

| Optimization | Metric | Tool |
|---|---|---|
| N+1 fix | DB query count per request | TypeORM logging / Prisma query events |
| DI fix | Service instantiation count | NestJS debug logs |
| Queue offloading | Request response time (ms) | NestJS interceptor timer |
| Guard deduplication | DB calls per request | Query logging middleware |
| Memory leak fix | RSS growth | `clinic.js heapprofiler` |
