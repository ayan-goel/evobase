"""Settings REST endpoints for per-repo budget and schedule configuration.

Routes:
  GET  /repos/{repo_id}/settings  — retrieve current settings (creates defaults on first access)
  PUT  /repos/{repo_id}/settings  — partial update; returns updated settings

These endpoints are used by the dashboard settings panel and by the scheduler
to read per-repo configuration.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repository, Settings
from app.db.session import get_db
from app.scheduling.auto_pause import unpause_repo
from app.settings.schemas import SettingsResponse, SettingsUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repos", tags=["settings"])


@router.get(
    "/{repo_id}/settings",
    response_model=SettingsResponse,
)
async def get_settings(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Retrieve settings for a repository.

    Creates a default Settings row on first access so callers always
    receive a valid response without requiring an explicit setup step.
    """
    # Verify repo exists
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    if not repo_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    result = await db.execute(
        select(Settings).where(Settings.repo_id == repo_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = Settings(repo_id=repo_id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return SettingsResponse.model_validate(settings)


@router.put(
    "/{repo_id}/settings",
    response_model=SettingsResponse,
)
async def update_settings(
    repo_id: uuid.UUID,
    body: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    """Partially update settings for a repository.

    Only fields included in the request body are modified.
    When `paused` is set to False, the failure counters are also reset so
    the repo gets a clean slate (equivalent to calling unpause).
    """
    # Verify repo exists
    repo_result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    if not repo_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {repo_id} not found",
        )

    result = await db.execute(
        select(Settings).where(Settings.repo_id == repo_id)
    )
    settings = result.scalar_one_or_none()

    if settings is None:
        settings = Settings(repo_id=repo_id)
        db.add(settings)

    # Apply partial updates
    if body.compute_budget_minutes is not None:
        settings.compute_budget_minutes = body.compute_budget_minutes
    if body.max_proposals_per_run is not None:
        settings.max_proposals_per_run = body.max_proposals_per_run
    if body.max_candidates_per_run is not None:
        settings.max_candidates_per_run = body.max_candidates_per_run
    if body.schedule is not None:
        settings.schedule = body.schedule
    if body.paused is not None:
        if body.paused is False and settings.paused is True:
            # Unpause: reset counters via the canonical helper
            await unpause_repo(db, repo_id)
            # Re-fetch since unpause_repo flushed changes
            await db.refresh(settings)
        else:
            settings.paused = body.paused
    if body.llm_provider is not None:
        settings.llm_provider = body.llm_provider
    if body.llm_model is not None:
        settings.llm_model = body.llm_model

    await db.commit()
    await db.refresh(settings)

    logger.info("Updated settings for repo %s", repo_id)
    return SettingsResponse.model_validate(settings)
