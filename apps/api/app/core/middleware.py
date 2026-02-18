"""ASGI middleware for the Coreloop API.

Three middlewares registered in order (outermost → innermost):
  1. CORSMiddleware     — handled by FastAPI directly (not here)
  2. RequestIdMiddleware — injects / forwards X-Request-ID; stores in ContextVar
  3. SecurityHeadersMiddleware — adds security response headers

The ContextVar `_request_id_var` is the single source of truth for the
current request ID. Both the logging layer and the runs router read it
so that every log line and every Run row share the same ID.
"""

import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# ---------------------------------------------------------------------------
# ContextVar — shared across middleware and route handlers within one request
# ---------------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """Return the current request's ID, or an empty string outside a request."""
    return _request_id_var.get()


# ---------------------------------------------------------------------------
# RequestIdMiddleware
# ---------------------------------------------------------------------------


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Read or generate X-Request-ID and make it available for the request lifetime.

    - If the client sends X-Request-ID, that value is reused (supports tracing
      across a frontend → API → worker chain).
    - If absent, a fresh UUID4 is generated.
    - The ID is always echoed back in the response header so callers can
      correlate their request logs with server-side logs.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind to ContextVar so any code running within this request can read it
        token = _request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security-related headers to every outgoing response.

    Header rationale:
      X-Content-Type-Options: nosniff
        — Prevents browsers from MIME-sniffing a response away from the
          declared Content-Type. Protects against content-injection attacks.

      X-Frame-Options: DENY
        — Blocks the page from being rendered in an iframe. Prevents
          clickjacking attacks. A CSP frame-ancestors directive is the
          modern equivalent, but this header provides defence-in-depth.

      Referrer-Policy: strict-origin-when-cross-origin
        — Sends full referrer within same origin, only origin across origins.
          Prevents leaking path/query-string to third-party services.

      X-XSS-Protection: 0
        — Explicitly disables the legacy XSS auditor (Chrome / Safari).
          The auditor has known bypasses and can itself be exploited.
          Content-Security-Policy is the correct modern protection.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        return response
