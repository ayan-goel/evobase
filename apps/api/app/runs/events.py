"""Redis Streams event bus for real-time run progress.

Events are published by the Celery worker (sync) and consumed by the
FastAPI SSE endpoint (async). Redis Streams provide ordered, persistent
(within TTL) delivery with replay support via stream IDs.

Stream key:   run_events:{run_id}
Cancel key:   run_cancel:{run_id}
Task ID key:  run_task:{run_id}
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

_STREAM_MAX_LEN = 500
_CANCEL_TTL_SECONDS = 3600
_TASK_ID_TTL_SECONDS = 7200

# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def _stream_key(run_id: str) -> str:
    return f"run_events:{run_id}"


def _cancel_key(run_id: str) -> str:
    return f"run_cancel:{run_id}"


def _task_id_key(run_id: str) -> str:
    return f"run_task:{run_id}"


# ---------------------------------------------------------------------------
# Sync client (used inside Celery worker)
# ---------------------------------------------------------------------------

_sync_redis = None


def _get_sync_redis():
    global _sync_redis
    if _sync_redis is None:
        import redis as _redis

        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _sync_redis = _redis.Redis.from_url(url, decode_responses=True)
    return _sync_redis


def publish_event(
    run_id: str,
    event_type: str,
    phase: str,
    data: Optional[dict[str, Any]] = None,
) -> str:
    """Publish a run event to the Redis Stream. Returns the stream entry ID."""
    r = _get_sync_redis()
    payload = {
        "type": event_type,
        "phase": phase,
        "ts": datetime.now(timezone.utc).isoformat(),
        "data": json.dumps(data or {}),
    }
    try:
        entry_id = r.xadd(
            _stream_key(run_id),
            payload,
            maxlen=_STREAM_MAX_LEN,
        )
        r.expire(_stream_key(run_id), 86400)
        return entry_id
    except Exception:
        logger.debug("Failed to publish event %s for run %s", event_type, run_id, exc_info=True)
        return ""


def set_cancel_flag(run_id: str) -> None:
    """Set the cancellation flag for a run."""
    r = _get_sync_redis()
    r.set(_cancel_key(run_id), "1", ex=_CANCEL_TTL_SECONDS)


def is_cancelled(run_id: str) -> bool:
    """Check whether a run has been cancelled."""
    r = _get_sync_redis()
    return r.exists(_cancel_key(run_id)) == 1


def store_task_id(run_id: str, task_id: str) -> None:
    """Store the Celery task ID so the cancel endpoint can revoke it."""
    r = _get_sync_redis()
    r.set(_task_id_key(run_id), task_id, ex=_TASK_ID_TTL_SECONDS)


def get_task_id(run_id: str) -> Optional[str]:
    """Retrieve the Celery task ID for a run."""
    r = _get_sync_redis()
    return r.get(_task_id_key(run_id))


# ---------------------------------------------------------------------------
# Async client (used by FastAPI SSE endpoint)
# ---------------------------------------------------------------------------

_async_redis = None


async def _get_async_redis():
    global _async_redis
    if _async_redis is None:
        import redis.asyncio as aioredis

        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _async_redis = aioredis.Redis.from_url(url, decode_responses=True)
    return _async_redis


async def event_stream(
    run_id: str,
    last_id: str = "0",
) -> AsyncIterator[dict[str, Any]]:
    """Async generator yielding events from a run's Redis Stream.

    Replays all events from *last_id* (exclusive), then blocks for new
    ones. Yields dicts with keys: id, type, phase, ts, data.
    """
    r = await _get_async_redis()
    key = _stream_key(run_id)
    cursor = last_id

    while True:
        try:
            results = await r.xread({key: cursor}, count=20, block=5000)
        except Exception:
            logger.debug("XREAD error for run %s", run_id, exc_info=True)
            break

        if results:
            for _stream_name, entries in results:
                for entry_id, fields in entries:
                    cursor = entry_id
                    yield {
                        "id": entry_id,
                        "type": fields.get("type", ""),
                        "phase": fields.get("phase", ""),
                        "ts": fields.get("ts", ""),
                        "data": json.loads(fields.get("data", "{}")),
                    }
        else:
            yield {"id": "", "type": "heartbeat", "phase": "", "ts": "", "data": {}}
