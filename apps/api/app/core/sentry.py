"""Sentry SDK integration for SelfOpt API.

Captures exceptions and performance traces without leaking secrets.

Key decisions:
  - `send_default_pii=False` — no user data sent by default.
  - `before_send` hook scrubs any event field whose key contains a
    sensitive keyword (api_key, secret, password, token, dsn).
  - `traces_sample_rate=0.1` — 10% of transactions sampled; adjust
    in production based on volume.
  - No-op when SENTRY_DSN is empty so the integration never raises in
    environments that don't configure it (local dev, CI).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Keywords that indicate a value should be redacted from Sentry events
_SENSITIVE_KEYS = frozenset({"api_key", "secret", "password", "token", "dsn"})


def _scrub_secrets(event: dict[str, Any], hint: Any) -> dict[str, Any]:
    """Sentry before_send hook: redact values for sensitive keys.

    Walks the event's `extra` and `request.data` dicts and replaces
    the values of any key matching a sensitive keyword with "[REDACTED]".
    This is a defence-in-depth measure; no real secret should appear in
    a Sentry event, but this ensures accidental logging cannot leak keys.
    """
    _scrub_dict(event.get("extra", {}))
    request_data = event.get("request", {}).get("data", {})
    if isinstance(request_data, dict):
        _scrub_dict(request_data)
    return event


def _scrub_dict(d: dict[str, Any]) -> None:
    """Recursively redact sensitive values in-place."""
    for key in list(d.keys()):
        if any(sensitive in key.lower() for sensitive in _SENSITIVE_KEYS):
            d[key] = "[REDACTED]"
        elif isinstance(d[key], dict):
            _scrub_dict(d[key])


def init_sentry(dsn: str, environment: str = "development") -> None:
    """Initialise the Sentry SDK.

    Called from `create_app()`. If `dsn` is empty, this is a no-op so
    local and CI environments are unaffected.

    Args:
        dsn: Sentry DSN string. Empty string disables Sentry entirely.
        environment: Sentry environment tag ("development" | "production").
    """
    if not dsn or not dsn.strip():
        logger.debug("Sentry DSN not configured — skipping initialisation")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
    except ImportError as exc:
        logger.warning("sentry-sdk not installed; Sentry disabled: %s", exc)
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_scrub_secrets,
    )
    logger.info("Sentry initialised (environment=%s)", environment)
