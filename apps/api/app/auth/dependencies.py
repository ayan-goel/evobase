"""Authentication stub for route guards.

In MVP, this is a placeholder that always returns a hardcoded user ID.
Supabase Auth integration will replace this with JWT validation.

Every protected endpoint must depend on `get_current_user` so that
the auth guard is already wired when real auth is added.
"""

import uuid

from fastapi import Header


# Deterministic test user ID matching seed data
STUB_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def get_current_user(
    authorization: str = Header(default="stub"),
) -> uuid.UUID:
    """Return the authenticated user's ID.

    Stub implementation: always returns the dev user.
    When Supabase Auth is integrated, this will:
    1. Extract the JWT from the Authorization header
    2. Verify the token with Supabase
    3. Return the user's UUID from the token claims
    """
    return STUB_USER_ID
