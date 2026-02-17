# =============================================================================
# SelfOpt API / Worker image
#
# Build context must be the monorepo root so we can COPY both apps/api and
# apps/runner into the image in a single stage.
#
# Example (from repo root):
#   docker build -f apps/api/Dockerfile -t selfopt-api .
# =============================================================================

FROM python:3.12-slim AS base

# System deps: git (cloning repos), build tools, libpq (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

WORKDIR /app

# ---------------------------------------------------------------------------
# Copy the runner package first (it is the editable local dependency)
# ---------------------------------------------------------------------------
COPY apps/runner /app/apps/runner

# ---------------------------------------------------------------------------
# Copy the API package
# ---------------------------------------------------------------------------
COPY apps/api /app/apps/api

# ---------------------------------------------------------------------------
# Install deps
# ---------------------------------------------------------------------------
# We resolve the local editable dependency inline:
#   uv pip install -e ../runner  then install selfopt-api
WORKDIR /app/apps/api

RUN uv pip install --system -e /app/apps/runner \
 && uv pip install --system .

# ---------------------------------------------------------------------------
# Non-root user for security
# ---------------------------------------------------------------------------
RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app
USER appuser

# Default entrypoint (overridden by docker-compose for the worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EXPOSE 8000
