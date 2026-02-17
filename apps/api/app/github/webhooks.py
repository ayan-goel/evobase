"""GitHub webhook handling.

Verifies webhook signatures and processes installation events.
The webhook secret is shared between GitHub and our app; it must
never be logged or exposed.

Signature verification uses HMAC-SHA256 as specified by GitHub:
https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
"""

import hashlib
import hmac

from app.core.config import get_settings


def verify_webhook_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify that a webhook payload was signed by GitHub.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of the X-Hub-Signature-256 header.

    Returns:
        True if the signature is valid, False otherwise.
    """
    settings = get_settings()
    if not settings.github_webhook_secret:
        raise ValueError("GITHUB_WEBHOOK_SECRET not configured")

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        settings.github_webhook_secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    received_signature = signature_header.removeprefix("sha256=")

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, received_signature)


def parse_installation_event(payload: dict) -> dict:
    """Extract relevant data from a GitHub App installation event.

    Returns a dict with installation_id, account info, and repo list.
    """
    action = payload.get("action", "")
    installation = payload.get("installation", {})

    return {
        "action": action,
        "installation_id": installation.get("id"),
        "account_login": installation.get("account", {}).get("login"),
        "account_id": installation.get("account", {}).get("id"),
        "repositories": [
            {
                "id": r["id"],
                "full_name": r["full_name"],
                "name": r["name"],
            }
            for r in payload.get("repositories", [])
        ],
    }
