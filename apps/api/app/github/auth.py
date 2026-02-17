"""GitHub App authentication.

Handles JWT generation for GitHub App auth and installation token exchange.
The private key is stored as an env var or file path — never in source control.

GitHub App auth flow:
1. Generate a JWT signed with the App's private key
2. Exchange the JWT for a short-lived installation access token
3. Use the installation token for API calls scoped to that installation
"""

import time

import jwt

from app.core.config import get_settings


def create_app_jwt() -> str:
    """Create a JWT for authenticating as the GitHub App.

    JWTs are valid for up to 10 minutes. We use 9 minutes
    to avoid clock-skew rejections.
    """
    settings = get_settings()

    if not settings.github_app_id or not settings.github_private_key:
        raise ValueError(
            "GitHub App credentials not configured. "
            "Set GITHUB_APP_ID and GITHUB_PRIVATE_KEY."
        )

    now = int(time.time())
    payload = {
        "iat": now - 60,  # Backdate 60s to handle clock skew
        "exp": now + (9 * 60),  # 9 minutes
        "iss": settings.github_app_id,
    }

    return jwt.encode(payload, settings.github_private_key, algorithm="RS256")
