# =============================================================================
# SelfOpt — combined API + worker image
#
# Build context must be the repository root so both apps/api and apps/runner
# are available in a single layer.
#
# Railway usage:
#   Single service running start.sh (FastAPI + Celery worker in one container)
#   PORT is injected automatically by Railway
# =============================================================================

FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# ---------------------------------------------------------------------------
# Install Python packages
# ---------------------------------------------------------------------------
COPY apps/runner /app/apps/runner
COPY apps/api    /app/apps/api
COPY start.sh    /app/start.sh

WORKDIR /app/apps/api

RUN uv pip install --system -e /app/apps/runner \
 && uv pip install --system .

RUN chmod +x /app/start.sh

# ---------------------------------------------------------------------------
# Non-root user
# ---------------------------------------------------------------------------
RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /app
USER appuser

# Railway injects $PORT; default to 8000 for local docker run
ENV PORT=8000
EXPOSE 8000

CMD ["/app/start.sh"]
