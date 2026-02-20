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
    RepoPatchRequest,
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


def _setup_failures_subq():
    """Correlated subquery returning consecutive_setup_failures for a repo."""
    return (
        select(Settings.consecutive_setup_failures)
        .where(Settings.repo_id == Repository.id)
        .correlate(Repository)
        .scalar_subquery()
        .label("setup_failures")
    )


def _build_repo_response(repo: Repository, latest_status, setup_failures) -> RepoResponse:
    return RepoResponse(
        **RepoResponse.model_validate(repo).model_dump(
            exclude={"latest_run_status", "setup_failing"}
        ),
        latest_run_status=latest_status,
        setup_failing=bool(setup_failures and setup_failures > 0),
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
        root_dir=body.root_dir or None,
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
    Each repo includes the status of its most recent run (or null if none)
    and a setup_failing flag derived from consecutive_setup_failures.
    """
    rows = (
        await db.execute(
            select(Repository, _latest_status_subq(), _setup_failures_subq())
            .join(Organization)
            .where(Organization.owner_id == user_id)
            .order_by(Repository.created_at.desc())
        )
    ).all()

    return RepoListResponse(
        repos=[
            _build_repo_response(repo, latest_status, setup_failures)
            for repo, latest_status, setup_failures in rows
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
            select(Repository, _latest_status_subq(), _setup_failures_subq())
            .join(Organization)
            .where(Repository.id == repo_id, Organization.owner_id == user_id)
        )
    ).one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    repo, latest_status, setup_failures = row
    return _build_repo_response(repo, latest_status, setup_failures)


@router.patch("/{repo_id}", response_model=RepoResponse)
async def patch_repo(
    repo_id: uuid.UUID,
    body: RepoPatchRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoResponse:
    """Update mutable repository configuration (root_dir and command overrides).

    Changing root_dir resets the consecutive_setup_failures counter so the
    runner gets a clean slate with the new directory on the next run.
    """
    row = (
        await db.execute(
            select(Repository, _setup_failures_subq())
            .join(Organization)
            .where(Repository.id == repo_id, Organization.owner_id == user_id)
        )
    ).one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    repo, setup_failures = row

    root_dir_changed = (
        body.root_dir is not None and body.root_dir != (repo.root_dir or "")
    )

    if body.root_dir is not None:
        repo.root_dir = body.root_dir or None
    if body.install_cmd is not None:
        repo.install_cmd = body.install_cmd or None
    if body.build_cmd is not None:
        repo.build_cmd = body.build_cmd or None
    if body.test_cmd is not None:
        repo.test_cmd = body.test_cmd or None
    if body.typecheck_cmd is not None:
        repo.typecheck_cmd = body.typecheck_cmd or None

    if root_dir_changed:
        settings_result = await db.execute(
            select(Settings).where(Settings.repo_id == repo_id)
        )
        settings = settings_result.scalar_one_or_none()
        if settings:
            settings.consecutive_setup_failures = 0
            settings.paused = False

    await db.commit()
    await db.refresh(repo)

    latest_status_row = (
        await db.execute(
            select(Run.status)
            .where(Run.repo_id == repo_id)
            .order_by(desc(Run.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()

    return _build_repo_response(repo, latest_status_row, 0 if root_dir_changed else setup_failures)
