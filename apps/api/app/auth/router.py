"""Auth endpoints for Supabase + GitHub OAuth integration.

POST /auth/github-callback is called by the frontend after Supabase
exchanges the OAuth code for a session. It upserts the user row with
GitHub metadata and ensures a default organization exists.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import GitHubCallbackRequest, GitHubCallbackResponse, MeResponse
from app.db.models import GitHubInstallation, Organization, User
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/github-callback",
    response_model=GitHubCallbackResponse,
)
async def github_callback(
    body: GitHubCallbackRequest,
    db: AsyncSession = Depends(get_db),
) -> GitHubCallbackResponse:
    """Upsert user with GitHub metadata and ensure a default org exists.

    Called by the frontend after Supabase completes the GitHub OAuth flow.
    Uses the Supabase UUID as the user's primary key so that JWTs issued
    by Supabase match the user row in our database.
    """
    user = None

    if body.supabase_user_id:
        result = await db.execute(
            select(User).where(User.id == body.supabase_user_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(
            select(User).where(User.github_id == body.github_id)
        )
        user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(
            select(User).where(User.email == body.email)
        )
        user = result.scalar_one_or_none()

    target_id = body.supabase_user_id or uuid.uuid4()

    if user and body.supabase_user_id and user.id != body.supabase_user_id:
        old_id = user.id
        logger.info(
            "Migrating user %s → %s (Supabase UUID)", old_id, body.supabase_user_id
        )
        orgs = (
            await db.execute(
                select(Organization).where(Organization.owner_id == old_id)
            )
        ).scalars().all()
        for org in orgs:
            org.owner_id = body.supabase_user_id

        installs = (
            await db.execute(
                select(GitHubInstallation).where(
                    GitHubInstallation.user_id == old_id
                )
            )
        ).scalars().all()
        for inst in installs:
            inst.user_id = body.supabase_user_id

        await db.flush()
        await db.delete(user)
        await db.flush()

        user = User(
            id=body.supabase_user_id,
            email=body.email,
            github_id=body.github_id,
            github_login=body.github_login,
            avatar_url=body.avatar_url,
        )
        db.add(user)
    elif user:
        user.github_id = body.github_id
        user.github_login = body.github_login
        user.avatar_url = body.avatar_url
        if body.email:
            user.email = body.email
    else:
        user = User(
            id=target_id,
            email=body.email,
            github_id=body.github_id,
            github_login=body.github_login,
            avatar_url=body.avatar_url,
        )
        db.add(user)

    await db.flush()

    result = await db.execute(
        select(Organization).where(Organization.owner_id == user.id)
    )
    org = result.scalars().first()

    if not org:
        org = Organization(name=body.github_login, owner_id=user.id)
        db.add(org)
        await db.flush()

    logger.info("GitHub callback: user=%s org=%s", user.id, org.id)

    return GitHubCallbackResponse(user_id=user.id, org_id=org.id)


@router.get("/me", response_model=MeResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user),
) -> MeResponse:
    """Return the authenticated user's IDs.

    Safe read-only alternative to calling /auth/github-callback just to
    retrieve the org_id. Requires a valid Supabase session token.
    """
    result = await db.execute(
        select(Organization).where(Organization.owner_id == user_id)
    )
    org = result.scalars().first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No organization found for this user",
        )
    return MeResponse(user_id=user_id, org_id=org.id)
