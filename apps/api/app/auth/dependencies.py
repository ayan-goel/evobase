"""Authentication dependency for route guards.

Validates Supabase-issued JWTs from the Authorization header and
ensures the corresponding user row exists in the database.
"""

import logging
import uuid

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> uuid.UUID:
    """Extract and validate a Supabase JWT, returning the user's UUID.

    On first authenticated request for a new user, an auto-created row is
    inserted so downstream queries never face a missing FK.
    """
    if not authorization.startswith("Bearer "):
        logger.warning("auth: missing or malformed Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        logger.warning("auth: empty token after Bearer prefix")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )

    secret = settings.supabase_jwt_secret
    if not secret:
        logger.error("auth: SUPABASE_JWT_SECRET is not configured")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        logger.warning("auth: JWT verification failed — %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No sub claim",
        )

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid sub claim",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        email = payload.get("email", f"{sub}@supabase.auth")
        db.add(User(id=user_id, email=email))
        await db.flush()

    return user_id
