"""Repository endpoints for the Control Plane API.

Handles connecting GitHub repos and retrieving repo details.
All endpoints require authentication via the auth dependency.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.models import Organization, Repository, Run, Settings
from app.db.session import get_db
from app.repos.schemas import (
    RepoConnectRequest,
    RepoConnectResponse,
    RepoListResponse,
    RepoResponse,
)
from app.runs.service import create_and_enqueue_run

router = APIRouter(prefix="/repos", tags=["repositories"])


def _latest_status_subq():
    """Correlated subquery that returns the most recent run status for a repo."""
    return (
        select(Run.status)
        .where(Run.repo_id == Repository.id)
        .order_by(desc(Run.created_at))
        .limit(1)
        .correlate(Repository)
        .scalar_subquery()
        .label("latest_run_status")
    )


@router.post(
    "/connect",
    response_model=RepoConnectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_repo(
    body: RepoConnectRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoConnectResponse:
    """Connect a GitHub repository to Coreloop.

    Creates a repository record, default settings, and auto-enqueues
    the first baseline run.  The org must exist and belong to the user.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == body.org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if org.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to add repos to this organization",
        )

    existing = await db.execute(
        select(Repository).where(Repository.github_repo_id == body.github_repo_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already connected",
        )

    repo = Repository(
        org_id=body.org_id,
        github_repo_id=body.github_repo_id,
        github_full_name=body.github_full_name,
        default_branch=body.default_branch,
        installation_id=body.installation_id,
        package_manager=body.package_manager,
        install_cmd=body.install_cmd,
        build_cmd=body.build_cmd,
        test_cmd=body.test_cmd,
        typecheck_cmd=body.typecheck_cmd,
        bench_config=body.bench_config,
    )
    db.add(repo)
    await db.flush()

    settings = Settings(repo_id=repo.id)
    db.add(settings)

    initial_run = await create_and_enqueue_run(db, repo.id)
    initial_run_id = str(initial_run.id)

    await db.commit()
    await db.refresh(repo)

    return RepoConnectResponse(
        **RepoResponse.model_validate(repo).model_dump(),
        initial_run_id=initial_run_id,
    )


@router.get("", response_model=RepoListResponse)
async def list_repos(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoListResponse:
    """List all repositories the authenticated user has access to.

    Returns repos belonging to organizations owned by the user, newest first.
    Each repo includes the status of its most recent run (or null if none).
    """
    rows = (
        await db.execute(
            select(Repository, _latest_status_subq())
            .join(Organization)
            .where(Organization.owner_id == user_id)
            .order_by(Repository.created_at.desc())
        )
    ).all()

    return RepoListResponse(
        repos=[
            RepoResponse(
                **RepoResponse.model_validate(repo).model_dump(exclude={"latest_run_status"}),
                latest_run_status=latest_status,
            )
            for repo, latest_status in rows
        ],
        count=len(rows),
    )


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoResponse:
    """Get details for a single repository, including latest run status."""
    row = (
        await db.execute(
            select(Repository, _latest_status_subq())
            .join(Organization)
            .where(Repository.id == repo_id, Organization.owner_id == user_id)
        )
    ).one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    repo, latest_status = row
    return RepoResponse(
        **RepoResponse.model_validate(repo).model_dump(exclude={"latest_run_status"}),
        latest_run_status=latest_status,
    )
