"""Celery application and configuration.

This is the single Celery app instance used by the entire control plane.
Workers are started with: celery -A app.engine.queue worker --loglevel=info

The broker and result backend both point to Redis.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "coreloop",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Global fallback time limits — the execute_run task sets its own (higher)
    # limits via @celery_app.task(..., soft_time_limit=..., time_limit=...).
    # These cover any short-lived Beat/scheduling tasks.
    task_soft_time_limit=120,
    task_time_limit=180,
    # Acknowledge tasks after they complete, not when received.
    # Prevents task loss if the worker crashes mid-execution.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # visibility_timeout MUST exceed the longest task's time_limit.
    # An agentic run can take up to ~1 hour (baseline + 10×LLM analysis +
    # patch generation + validation). Set to 2 hours to be safe.
    # If this is shorter than time_limit, Redis re-delivers the task while
    # it is still running, causing spurious duplicate executions.
    broker_transport_options={"visibility_timeout": 7200},
)

# Auto-discover tasks in engine and scheduling modules
celery_app.autodiscover_tasks(["app.engine", "app.scheduling"])


# ---------------------------------------------------------------------------
# Worker startup: verify DB connectivity so we fail fast if Postgres is
# unreachable instead of silently hanging on the first task.
# ---------------------------------------------------------------------------
from celery.signals import worker_ready  # noqa: E402

@worker_ready.connect
def _check_db_on_startup(**kwargs):
    import logging
    _logger = logging.getLogger(__name__)
    try:
        from app.db.sync_session import get_sync_db
        with get_sync_db() as session:
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
        _logger.info("Worker DB health check passed")
    except Exception as exc:
        _logger.error("Worker DB health check FAILED: %s", exc)
