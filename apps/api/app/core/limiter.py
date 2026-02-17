"""SlowAPI rate limiter singleton.

The limiter is keyed on the authenticated user ID so limits apply per-user,
not per-IP (which would incorrectly penalise users behind NAT/proxies).

Usage in route handlers:
    from app.core.limiter import limiter
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    @router.post("/some-endpoint")
    @limiter.limit(settings.run_rate_limit)
    async def handler(request: Request, ...):
        ...

The `Request` parameter is required by SlowAPI even if the handler doesn't
use it directly — it uses it to extract the key.
"""

from slowapi import Limiter


def _user_id_key(request) -> str:
    """Key function: rate-limit per authenticated user ID.

    Falls back to client IP if the user ID is not yet resolved
    (e.g., unauthenticated routes).
    """
    # user_id is injected by get_current_user dependency and stored on
    # request.state by the auth middleware (or resolved inline).
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return str(user_id)
    # Fallback: IP address (covers unauthenticated preflight requests)
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_user_id_key, default_limits=[])
