"""Repository endpoints for the Control Plane API.

Handles connecting GitHub repos and retrieving repo details.
All endpoints require authentication via the auth dependency.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.models import Organization, Repository, Settings
from app.db.session import get_db
from app.repos.schemas import RepoConnectRequest, RepoListResponse, RepoResponse

router = APIRouter(prefix="/repos", tags=["repositories"])


@router.post(
    "/connect",
    response_model=RepoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def connect_repo(
    body: RepoConnectRequest,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoResponse:
    """Connect a GitHub repository to SelfOpt.

    Creates a repository record and default settings.
    The org must exist and belong to the authenticated user.
    """
    # Verify the organization exists and the user owns it
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

    # Check for duplicate github_repo_id
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
        package_manager=body.package_manager,
        install_cmd=body.install_cmd,
        build_cmd=body.build_cmd,
        test_cmd=body.test_cmd,
        typecheck_cmd=body.typecheck_cmd,
        bench_config=body.bench_config,
    )
    db.add(repo)
    await db.flush()

    # Create default settings for the new repository
    settings = Settings(repo_id=repo.id)
    db.add(settings)

    await db.commit()
    await db.refresh(repo)
    return RepoResponse.model_validate(repo)


@router.get("", response_model=RepoListResponse)
async def list_repos(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoListResponse:
    """List all repositories the authenticated user has access to.

    Returns repos belonging to organizations owned by the user.
    """
    result = await db.execute(
        select(Repository)
        .join(Organization)
        .where(Organization.owner_id == user_id)
        .order_by(Repository.created_at.desc())
    )
    repos = result.scalars().all()
    return RepoListResponse(
        repos=[RepoResponse.model_validate(r) for r in repos],
        count=len(repos),
    )


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(
    repo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> RepoResponse:
    """Get details for a single repository."""
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
    return RepoResponse.model_validate(repo)
