"""Structured JSON logging via structlog.

Configures structlog once at application startup. All subsequent calls to
`structlog.get_logger()` (or `logging.getLogger()` via the stdlib bridge)
will use this configuration.

Renderer selection:
  debug=True  — `ConsoleRenderer` with colours for local development.
  debug=False — `JSONRenderer` for machine-parseable logs in production.

ContextVar injection:
  The `request_id` and `trace_id` fields are injected into every log line
  from `app.core.middleware._request_id_var` and a trace ID context var.
  This means any logger called inside a request handler automatically
  includes the request ID without the developer having to pass it manually.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

from app.core.middleware import get_request_id

# Optional trace_id ContextVar — set by the runs router when processing a run
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Return the current trace ID, or empty string if not set."""
    return _trace_id_var.get()


def _inject_context_vars(
    logger: logging.Logger,
    method: str,
    event_dict: dict,
) -> dict:
    """Structlog processor: inject request_id and trace_id from ContextVars."""
    request_id = get_request_id()
    trace_id = get_trace_id()
    if request_id:
        event_dict["request_id"] = request_id
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def configure_structlog(debug: bool = True) -> None:
    """Configure structlog for the application lifetime.

    Call once from `create_app()` before any routers are registered.
    Calling multiple times is safe — structlog is idempotent.
    """
    shared_processors: list = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _inject_context_vars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if debug:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging → structlog so third-party libraries (SQLAlchemy,
    # httpx, etc.) also produce structured output.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )
