"""Supabase Storage integration for artifact management.

Generates short-lived signed URLs for downloading stored artifacts.
The service role key is used server-side only — it is never sent to
the frontend.

Security:
  - `_validate_path()` rejects any path containing `..` or null bytes
    to prevent path traversal attacks.
  - Falls back gracefully to None when Supabase is not configured
    (local development, CI) rather than raising.

Configuration:
  SUPABASE_URL          — Supabase project URL
  SUPABASE_SERVICE_KEY  — Service role key (required for signed URLs)
  STORAGE_BUCKET        — Bucket name (default: "artifacts")
"""

from __future__ import annotations

import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _validate_path(path: str) -> None:
    """Reject paths that could be used for path traversal.

    Checks for:
      - `..` components (relative path traversal)
      - Null bytes (can terminate strings in C-level filesystem calls)

    Args:
        path: Storage path to validate.

    Raises:
        ValueError: If the path contains invalid components.
    """
    if not path:
        raise ValueError("Storage path must not be empty")
    if ".." in path:
        raise ValueError(
            f"Invalid storage path — path traversal detected: {path!r}"
        )
    if "\x00" in path:
        raise ValueError(
            f"Invalid storage path — null byte detected: {path!r}"
        )


async def generate_signed_url(
    storage_path: str,
    expires_in: int = 3600,
) -> Optional[str]:
    """Generate a Supabase Storage signed URL for downloading an artifact.

    Args:
        storage_path: Path within the configured storage bucket, e.g.
                      "runs/abc123/diff.patch".
        expires_in: URL validity window in seconds (default: 1 hour).

    Returns:
        A signed URL string, or None if Supabase is not configured.

    Raises:
        ValueError: If storage_path fails validation (path traversal guard).
    """
    _validate_path(storage_path)

    settings = get_settings()

    if not settings.supabase_service_key:
        logger.debug(
            "SUPABASE_SERVICE_KEY not configured — skipping signed URL generation"
        )
        return None

    try:
        from supabase import create_client  # noqa: PLC0415 — lazy import avoids hard dep

        client = create_client(settings.supabase_url, settings.supabase_service_key)
        result = client.storage.from_(settings.storage_bucket).create_signed_url(
            storage_path, expires_in
        )

        # supabase-py v1 returns a dict; v2 returns a SignedURL object.
        if isinstance(result, dict):
            signed_url: Optional[str] = result.get("signedURL") or result.get("signedUrl")
        else:
            signed_url = getattr(result, "signed_url", None)

        if signed_url:
            return signed_url

        logger.warning(
            "Supabase returned no signed URL for path '%s': %s",
            storage_path, result,
        )
        return None

    except ImportError:
        logger.warning("supabase package not installed — cannot generate signed URL")
        return None
    except Exception as exc:
        logger.error(
            "Failed to generate signed URL for '%s': %s",
            storage_path, exc,
        )
        return None
