"""Run endpoints for the Control Plane API.

Handles enqueueing optimization runs, retrieving run history,
streaming live run events via SSE, and cancelling runs.

Rate limiting: POST /repos/{repo_id}/run is throttled via SlowAPI.
The limit is configurable in settings (default: 10/minute per user).
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import decode_token, get_current_user
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.middleware import get_request_id
from app.db.models import Organization, Repository, Run
from app.db.session import get_db
from app.runs.schemas import (
    RunCancelResponse,
    RunCreateRequest,
    RunListResponse,
    RunResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["runs"])


async def _get_run_for_user(
    run_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Run:
    """Fetch a run by ID, enforcing owner-level access. Raises 404 if not found."""
    result = await db.execute(
        select(Run)
        .join(Repository)
        .join(Organization)
        .where(Run.id == run_id, Organization.owner_id == user_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.post(
    "/repos/{repo_id}/run",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(settings.run_rate_limit)
async def enqueue_run(
    request: Request,
    repo_id: uuid.UUID,
    body: RunCreateRequest = RunCreateRequest(),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RunResponse:
    """Enqueue a new optimization run for a repository."""
    request.state.user_id = user_id

    result = await db.execute(
        select(Repository)
        .join(Organization)
        .where(Repository.id == repo_id, Organization.owner_id == user_id)
    )
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    trace_id = get_request_id() or str(uuid.uuid4())

    from app.runs.service import create_and_enqueue_run

    run = await create_and_enqueue_run(db, repo_id, sha=body.sha, trace_id=trace_id)
    await db.commit()
    await db.refresh(run)
    logger.info("Enqueued run %s (trace_id=%s)", run.id, trace_id)

    return RunResponse.model_validate(run)


@router.get("/repos/{repo_id}/runs", response_model=RunListResponse)
async def list_runs(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RunListResponse:
    """List all runs for a repository, newest first."""
    result = await db.execute(
        select(Repository)
        .join(Organization)
        .where(Repository.id == repo_id, Organization.owner_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    result = await db.execute(
        select(Run)
        .where(Run.repo_id == repo_id)
        .order_by(Run.created_at.desc())
    )
    runs = result.scalars().all()
    return RunListResponse(
        runs=[RunResponse.model_validate(r) for r in runs],
        count=len(runs),
    )


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RunResponse:
    """Fetch a single run by ID."""
    run = await _get_run_for_user(run_id, user_id, db)
    return RunResponse.model_validate(run)


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: uuid.UUID,
    request: Request,
    token: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Stream run events via Server-Sent Events.

    Replays all historical events, then blocks for new ones.
    Sends heartbeat comments every 5s to keep the connection alive.
    Respects Last-Event-ID header for reconnection.

    Auth: Accepts token as query param (EventSource can't set headers).
    """
    auth_token = token or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    try:
        payload = await decode_token(auth_token, get_settings())
        sub = payload.get("sub", "")
        user_id = uuid.UUID(sub)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    await _get_run_for_user(run_id, user_id, db)

    last_event_id = request.headers.get("Last-Event-ID", "0")

    async def _generate():
        from app.runs.events import event_stream

        terminal_seen = False
        heartbeat_count = 0

        async for event in event_stream(str(run_id), last_id=last_event_id):
            if await request.is_disconnected():
                break

            if event["type"] == "heartbeat":
                heartbeat_count += 1
                yield f": heartbeat {heartbeat_count}\n\n"
                # Check DB for terminal status after heartbeats
                if heartbeat_count % 3 == 0 and not terminal_seen:
                    from sqlalchemy import select as sa_select
                    from app.db.session import async_session_factory
                    async with async_session_factory() as check_session:
                        check_result = await check_session.execute(
                            sa_select(Run.status).where(Run.id == run_id)
                        )
                        current_status = check_result.scalar_one_or_none()
                        if current_status in ("completed", "failed"):
                            terminal_seen = True
                if terminal_seen:
                    yield f"event: done\ndata: {{}}\n\n"
                    break
                continue

            event_data = json.dumps(event)
            entry_id = event["id"]
            yield f"id: {entry_id}\nevent: run_event\ndata: {event_data}\n\n"

            if event["type"] in ("run.completed", "run.failed", "run.cancelled"):
                terminal_seen = True
                yield f"event: done\ndata: {{}}\n\n"
                break

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> None:
    """Permanently delete a run and all associated proposals/events."""
    run = await _get_run_for_user(run_id, user_id, db)

    if run.status in ("queued", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an active run. Cancel it first.",
        )

    await db.delete(run)
    await db.commit()
    logger.info("Run %s deleted by user %s", run_id, user_id)


@router.post("/runs/{run_id}/cancel", response_model=RunCancelResponse)
async def cancel_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RunCancelResponse:
    """Cancel a queued or running run.

    Sets a cancellation flag in Redis, revokes the Celery task (if running),
    and transitions the run to 'failed' status.
    """
    run = await _get_run_for_user(run_id, user_id, db)

    if run.status not in ("queued", "running"):
        return RunCancelResponse(
            run_id=run_id,
            status=run.status,
            cancelled=False,
        )

    from app.runs.events import get_task_id, publish_event, set_cancel_flag

    set_cancel_flag(str(run_id))

    task_id = get_task_id(str(run_id))
    if task_id:
        try:
            from app.engine.queue import celery_app
            celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
            logger.info("Revoked Celery task %s for run %s", task_id, run_id)
        except Exception:
            logger.warning("Failed to revoke task %s", task_id, exc_info=True)

    run.status = "failed"
    await db.flush()
    await db.commit()

    publish_event(str(run_id), "run.cancelled", "run", {"reason": "User cancelled"})
    logger.info("Run %s cancelled by user %s", run_id, user_id)

    return RunCancelResponse(
        run_id=run_id,
        status="failed",
        cancelled=True,
    )
