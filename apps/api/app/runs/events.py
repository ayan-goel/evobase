"""Redis Streams event bus for real-time run progress.

Events are published by the Celery worker (sync) and consumed by the
FastAPI SSE endpoint (async). Redis Streams provide ordered, low-latency
delivery during an active run.

Every event is *also* persisted to the ``run_events`` Postgres table so
that the full event timeline is always available for historical views,
even after the Redis stream's TTL has expired.

event_stream() replay strategy
────────────────────────────────
1. Replay all stored events from Postgres (instant for completed runs).
2. For completed / failed runs: done — yield the Postgres rows and exit.
3. For active runs: continue reading from the Redis Stream starting from
   the *stream_id* of the last Postgres event, deduplicating by pg_id to
   prevent double-delivery of events that were already replayed.

Stream key:   run_events:{run_id}
Cancel key:   run_cancel:{run_id}
Task ID key:  run_task:{run_id}
"""

import json
import logging
import os
import uuid as _uuid_mod
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)

_STREAM_MAX_LEN = 5000
# Redis stream TTL: 7 days (serves as a cache for live/recent runs).
# Postgres is the permanent store; Redis TTL only affects live streaming
# for very old in-progress runs, which is not a realistic scenario.
_STREAM_TTL_SECONDS = 7 * 24 * 60 * 60
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
    """Publish a run event to Redis Stream *and* persist it to Postgres.

    Returns the Redis Stream entry ID, or "" on Redis failure.

    Postgres write is best-effort: a DB error never propagates to the
    caller so that a transient DB hiccup cannot abort the pipeline.
    The Redis write follows the same contract as before.
    """
    r = _get_sync_redis()
    now_ts = datetime.now(timezone.utc).isoformat()
    event_id = str(_uuid_mod.uuid4())

    # ------------------------------------------------------------------
    # 1. Publish to Redis Stream (include pg_id so the SSE endpoint can
    #    deduplicate events that were already delivered via Postgres replay)
    # ------------------------------------------------------------------
    payload = {
        "pg_id": event_id,
        "type": event_type,
        "phase": phase,
        "ts": now_ts,
        "data": json.dumps(data or {}),
    }
    stream_entry_id = ""
    try:
        key = _stream_key(run_id)
        pipe = r.pipeline()
        pipe.xadd(key, payload, maxlen=_STREAM_MAX_LEN)
        pipe.expire(key, _STREAM_TTL_SECONDS)
        results = pipe.execute()
        stream_entry_id = results[0]
    except Exception:
        logger.debug(
            "Failed to publish event %s to Redis for run %s",
            event_type, run_id, exc_info=True,
        )

    # ------------------------------------------------------------------
    # 2. Persist to Postgres (best-effort)
    # ------------------------------------------------------------------
    try:
        from app.db.models import RunEvent
        from app.db.sync_session import get_sync_db

        with get_sync_db() as session:
            row = RunEvent(
                id=_uuid_mod.UUID(event_id),
                run_id=_uuid_mod.UUID(run_id),
                event_type=event_type,
                phase=phase,
                data=data or {},
                stream_id=stream_entry_id or None,
            )
            session.add(row)
            session.commit()
    except Exception:
        logger.debug(
            "Failed to persist event %s to DB for run %s",
            event_type, run_id, exc_info=True,
        )

    return stream_entry_id


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


def _is_uuid(value: str) -> bool:
    """Return True if *value* is a valid UUID string."""
    try:
        _uuid_mod.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


async def event_stream(
    run_id: str,
    last_id: str = "0",
    run_status: str = "running",
) -> AsyncIterator[dict[str, Any]]:
    """Async generator yielding events for a run.

    Phase 1 — Postgres replay
    ─────────────────────────
    All persisted events are read from the ``run_events`` table in
    chronological order.  If *last_id* is a UUID, replay starts *after*
    the matching row so reconnection is seamless.

    Phase 2 — Completed / failed runs
    ───────────────────────────────────
    If the run is in a terminal state (completed / failed), the generator
    returns after the Postgres replay; the caller is responsible for sending
    the SSE ``done`` event.

    Phase 3 — Active runs: live Redis stream
    ─────────────────────────────────────────
    For still-running runs we continue reading from the Redis Stream starting
    at the ``stream_id`` of the last Postgres event.  Any event whose
    ``pg_id`` was already sent in Phase 1 is skipped to prevent duplicates.
    Heartbeats are yielded when there are no new events within the block
    window so the HTTP connection is kept alive.
    """
    from sqlalchemy import select as sa_select

    from app.db.models import RunEvent
    from app.db.session import async_session_factory

    # -----------------------------------------------------------------------
    # Phase 1: Postgres replay
    # -----------------------------------------------------------------------
    seen_pg_ids: set[str] = set()
    last_redis_cursor = "0"

    try:
        async with async_session_factory() as pg_session:
            query = sa_select(RunEvent).where(
                RunEvent.run_id == _uuid_mod.UUID(run_id)
            )

            # Resume from after a specific event when the client reconnects
            if last_id and last_id != "0" and _is_uuid(last_id):
                ref = await pg_session.get(RunEvent, _uuid_mod.UUID(last_id))
                if ref is not None:
                    query = query.where(RunEvent.ts > ref.ts)

            query = query.order_by(RunEvent.ts)
            result = await pg_session.execute(query)
            rows = result.scalars().all()

            for row in rows:
                pg_id = str(row.id)
                seen_pg_ids.add(pg_id)
                if row.stream_id:
                    last_redis_cursor = row.stream_id
                yield {
                    "id": pg_id,
                    "type": row.event_type,
                    "phase": row.phase,
                    "ts": row.ts.isoformat(),
                    "data": row.data,
                }
    except Exception:
        logger.debug(
            "Postgres replay failed for run %s", run_id, exc_info=True
        )

    # -----------------------------------------------------------------------
    # Phase 2: Terminal runs — Postgres is the complete record
    # -----------------------------------------------------------------------
    if run_status in ("completed", "failed"):
        return

    # -----------------------------------------------------------------------
    # Phase 3: Active runs — continue from Redis live stream
    # -----------------------------------------------------------------------
    r = await _get_async_redis()
    key = _stream_key(run_id)
    cursor = last_redis_cursor

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
                    pg_id = fields.get("pg_id", "")
                    # Skip events already delivered via Postgres replay
                    if pg_id and pg_id in seen_pg_ids:
                        continue
                    if pg_id:
                        seen_pg_ids.add(pg_id)
                    yield {
                        # Prefer the Postgres UUID as the stable event ID;
                        # fall back to the Redis stream entry ID so the SSE
                        # client always has something to track.
                        "id": pg_id or entry_id,
                        "type": fields.get("type", ""),
                        "phase": fields.get("phase", ""),
                        "ts": fields.get("ts", ""),
                        "data": json.loads(fields.get("data", "{}")),
                    }
        else:
            yield {"id": "", "type": "heartbeat", "phase": "", "ts": "", "data": {}}
