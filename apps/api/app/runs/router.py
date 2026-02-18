"""Run endpoints for the Control Plane API.

Handles enqueueing optimization runs and retrieving run history.

Rate limiting: POST /repos/{repo_id}/run is throttled via SlowAPI.
The limit is configurable in settings (default: 10/minute per user).
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.middleware import get_request_id
from app.db.models import Organization, Repository, Run
from app.db.session import get_db
from app.runs.schemas import RunCreateRequest, RunListResponse, RunResponse

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["runs"])


@router.post(
    "/repos/{repo_id}/run",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(settings.run_rate_limit)
async def enqueue_run(
    request: Request,  # Required by SlowAPI for rate-limit key extraction
    repo_id: uuid.UUID,
    body: RunCreateRequest = RunCreateRequest(),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RunResponse:
    """Enqueue a new optimization run for a repository.

    Creates a run record with status 'queued' and dispatches
    a Celery task for background execution.

    Rate limited: 10 requests/minute per authenticated user.
    """
    # Bind user_id to request.state so the rate limiter key function can use it
    request.state.user_id = user_id

    # Verify repo exists and user has access
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

    # Inherit the request trace ID so the run is greppable in logs
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
    # Verify repo exists and user has access
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
