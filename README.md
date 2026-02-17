# SelfOpt

Autonomous code optimization system. Connect your repo, come back later, review real improvements.

## Architecture

- **apps/web** — Next.js 15 dashboard (App Router, Tailwind, shadcn/ui)
- **apps/api** — FastAPI control plane (Pydantic v2, SQLAlchemy 2.0 async)
- **apps/runner** — Sandbox execution engine (Python)
- **infra/supabase** — Database schema and migrations (Supabase CLI)

## Prerequisites

- Node.js 20+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Supabase CLI](https://supabase.com/docs/guides/cli)
- Docker (for Redis and optional containerized dev)

## Local Development

### 1. Start Supabase (Postgres + Storage + Auth)

```bash
cd infra/supabase
supabase start
```

### 2. Start Redis

```bash
docker compose up redis -d
```

### 3. Start the API

```bash
cd apps/api
cp ../../.env.example .env  # Edit with your Supabase keys from `supabase status`
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Start the Dashboard

```bash
cd apps/web
npm run dev
```

## Running Tests

```bash
# API tests
cd apps/api && uv run pytest tests/ -v

# Runner tests
cd apps/runner && uv run pytest tests/ -v

# Web tests
cd apps/web && npm test
```
