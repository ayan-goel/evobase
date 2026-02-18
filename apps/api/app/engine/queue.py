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
)

# Auto-discover tasks in engine and scheduling modules
celery_app.autodiscover_tasks(["app.engine", "app.scheduling"])
