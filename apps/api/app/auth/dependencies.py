"""Authentication dependency for route guards.

Validates Supabase-issued JWTs from the Authorization header and
ensures the corresponding user row exists in the database.

Supabase projects created after mid-2025 use ECC P-256 (ES256) signing
keys by default. Older projects used a shared HS256 secret. This module
supports both by reading the algorithm from the JWT header and verifying
against either the shared secret (HS256) or the JWKS endpoint (ES256).
"""

import logging
import uuid

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger(__name__)

STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Module-level JWKS cache — fetched once per process, refreshed on decode error.
_jwks_cache: dict | None = None


async def _fetch_jwks(supabase_url: str) -> dict:
    """Fetch and cache Supabase's public JWKS for ES256 verification."""
    global _jwks_cache
    if _jwks_cache is None:
        url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url)
            res.raise_for_status()
            _jwks_cache = res.json()
        logger.info("auth: fetched JWKS from %s (%d keys)", url, len(_jwks_cache.get("keys", [])))
    return _jwks_cache


async def _decode_jwt(token: str, settings: Settings) -> dict:
    """Verify a Supabase JWT using HS256 (legacy) or ES256 (current ECC key)."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError(f"Malformed token header: {exc}") from exc

    alg = header.get("alg", "HS256")

    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise JWTError("SUPABASE_JWT_SECRET is not configured")
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )

    if alg == "ES256":
        global _jwks_cache
        jwks = await _fetch_jwks(settings.supabase_url)
        try:
            return jwt.decode(
                token,
                jwks,
                algorithms=["ES256"],
                audience="authenticated",
            )
        except JWTError:
            # JWKS may be stale (key rotation) — clear cache and retry once.
            _jwks_cache = None
            jwks = await _fetch_jwks(settings.supabase_url)
            return jwt.decode(
                token,
                jwks,
                algorithms=["ES256"],
                audience="authenticated",
            )

    raise JWTError(f"Unsupported algorithm: {alg}")


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

    try:
        payload = await _decode_jwt(token, settings)
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
