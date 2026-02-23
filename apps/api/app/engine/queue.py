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
    # Limit task execution time to prevent runaway processes.
    # Individual tasks can override with their own soft/hard limits.
    task_soft_time_limit=600,
    task_time_limit=660,
    # Acknowledge tasks after they complete, not when received.
    # Prevents task loss if the worker crashes mid-execution.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Re-deliver unacked tasks after 5 minutes (default is 1 hour).
    # Keeps recovery fast after worker crashes or deployments.
    broker_transport_options={"visibility_timeout": 300},
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
