# Framework Support — Overview

This document describes the current state of framework detection, what frameworks we plan to support, what the UI should show per framework, and how the optimization agent tailors its analysis per stack.

---

## Current State

The detector (`apps/runner/runner/detector/`) handles JavaScript/TypeScript projects only:

| Framework | Detected via | Agent focus prompt |
|---|---|---|
| Next.js | `next` in deps | Yes — detailed |
| NestJS | `@nestjs/core` in deps | Yes — detailed |
| Express | `express` in deps | Yes — detailed |
| React + Vite | `vite` or `react` in deps | Yes — detailed |
| Nuxt | `nuxt` in deps | No (falls through to generic) |
| Gatsby | `gatsby` in deps | No |
| Remix | `remix` in deps | No |
| Angular | `@angular/core` in deps | No |
| Svelte | `svelte` in deps | No |
| Vue | `vue` in deps | No |
| Fastify | `fastify` in deps | No |
| Koa | `koa` in deps | No |
| Hapi | `hapi` in deps | No |

Python, Go, Rust, Ruby, and Java projects are **not detected at all** — the runner assumes a JS/TS codebase for detection and install commands.

---

## Target Framework Matrix

The following table defines the target state. Every framework in this list should have:
1. Detection logic in the runner
2. A framework-specific system prompt
3. A framework logo shown in the UI
4. A dedicated strategy document in `markdown/strategies/`

### JavaScript / TypeScript — Frontend

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| Next.js | `next` dep | next.svg | [nextjs.md](strategies/nextjs.md) |
| React (Vite/CRA) | `react` + `vite` or `react-scripts` | react.svg | [react.md](strategies/react.md) |
| Vue.js | `vue` dep | vue.svg | [vue-nuxt.md](strategies/vue-nuxt.md) |
| Nuxt | `nuxt` dep | nuxt.svg | [vue-nuxt.md](strategies/vue-nuxt.md) |
| Angular | `@angular/core` dep | angular.svg | [angular.md](strategies/angular.md) |
| Svelte | `svelte` dep | svelte.svg | [svelte-sveltekit.md](strategies/svelte-sveltekit.md) |
| SvelteKit | `@sveltejs/kit` dep | svelte.svg | [svelte-sveltekit.md](strategies/svelte-sveltekit.md) |
| Remix | `@remix-run/react` dep | remix.svg | — |
| Gatsby | `gatsby` dep | gatsby.svg | — |
| Astro | `astro` dep | astro.svg | — |
| Solid.js | `solid-js` dep | solid.svg | — |

### JavaScript / TypeScript — Backend

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| Express | `express` dep | express.svg | [express-node.md](strategies/express-node.md) |
| NestJS | `@nestjs/core` dep | nestjs.svg | [nestjs.md](strategies/nestjs.md) |
| Fastify | `fastify` dep | fastify.svg | — |
| Koa | `koa` dep | nodejs.svg | — |
| Hapi | `hapi` dep | nodejs.svg | — |
| tRPC | `@trpc/server` dep | trpc.svg | — |

### Python

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| FastAPI | `fastapi` in pyproject.toml / requirements.txt | fastapi.svg | [fastapi.md](strategies/fastapi.md) |
| Django | `django` in pyproject.toml / requirements.txt | django.svg | [django.md](strategies/django.md) |
| Flask | `flask` in pyproject.toml / requirements.txt | flask.svg | [flask.md](strategies/flask.md) |
| Starlette | `starlette` in deps | python.svg | — |
| Litestar | `litestar` in deps | python.svg | — |

### Go

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| Go (any) | `go.mod` exists | go.svg | [go.md](strategies/go.md) |
| Gin | `gin-gonic/gin` in go.mod | go.svg | [go.md](strategies/go.md) |
| Echo | `labstack/echo` in go.mod | go.svg | [go.md](strategies/go.md) |
| Fiber | `gofiber/fiber` in go.mod | go.svg | [go.md](strategies/go.md) |

### Rust

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| Rust (any) | `Cargo.toml` exists | rust.svg | [rust.md](strategies/rust.md) |
| Axum | `axum` in Cargo.toml | rust.svg | [rust.md](strategies/rust.md) |
| Actix | `actix-web` in Cargo.toml | rust.svg | [rust.md](strategies/rust.md) |

### Ruby

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| Rails | `rails` in Gemfile | rails.svg | [rails.md](strategies/rails.md) |
| Sinatra | `sinatra` in Gemfile | ruby.svg | — |

### JVM

| Framework | Detection method | Logo | Strategy doc |
|---|---|---|---|
| Spring Boot | `spring-boot` in pom.xml / build.gradle | spring.svg | [spring-boot.md](strategies/spring-boot.md) |
| Quarkus | `quarkus` in pom.xml | quarkus.svg | — |
| Micronaut | `micronaut` in pom.xml | java.svg | — |

---

## Detection Priority

When a project contains signals for multiple frameworks (e.g. a Next.js monorepo with a FastAPI backend), the detector should return the most specific match based on the `root_dir` in use. The priority order within each ecosystem should be:

1. Most specific framework match (e.g. `nextjs` > `react`)
2. Higher confidence signal (lock file > dep > fallback)

---

## What the UI Shows

See [framework-logos-ui.md](framework-logos-ui.md) for the full UI specification.

The short version:
- **Repository card** (dashboard): Small framework icon badge bottom-right of the card
- **Repository detail page**: Larger framework badge next to the repo name, plus package manager badge
- **Run detail**: Framework badge in the run header
- **Connect repo / picker**: Framework auto-detected and shown inline after connection
