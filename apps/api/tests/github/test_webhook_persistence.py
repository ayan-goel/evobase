"""Tests for webhook installation persistence in the database.

Verifies that installation created/deleted events result in correct
github_installations rows being created or removed.
"""

import hashlib
import hmac
import json
import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GitHubInstallation
from tests.conftest import STUB_USER_ID


def _make_installation_payload(
    action: str = "created",
    installation_id: int = 42000,
    account_login: str = "testorg",
    account_id: int = 100,
    repos: list | None = None,
) -> dict:
    return {
        "action": action,
        "installation": {
            "id": installation_id,
            "account": {"login": account_login, "id": account_id},
        },
        "repositories": repos or [],
    }


class TestWebhookInstallationPersistence:
    @patch("app.github.router.verify_webhook_signature", return_value=True)
    async def test_installation_created_event_persists_row(
        self, mock_verify, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        payload = _make_installation_payload(
            action="created", installation_id=55000, account_login="myorg", account_id=200
        )
        res = await seeded_client.post(
            "/github/webhooks",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200

        result = await seeded_db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == 55000
            )
        )
        inst = result.scalar_one_or_none()
        assert inst is not None
        assert inst.account_login == "myorg"
        assert inst.account_id == 200

    @patch("app.github.router.verify_webhook_signature", return_value=True)
    async def test_installation_created_event_is_idempotent(
        self, mock_verify, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        payload = _make_installation_payload(installation_id=56000)
        headers = {
            "X-Hub-Signature-256": "sha256=valid",
            "X-GitHub-Event": "installation",
            "Content-Type": "application/json",
        }

        await seeded_client.post("/github/webhooks", content=json.dumps(payload), headers=headers)
        await seeded_client.post("/github/webhooks", content=json.dumps(payload), headers=headers)

        result = await seeded_db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == 56000
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1

    @patch("app.github.router.verify_webhook_signature", return_value=True)
    async def test_installation_deleted_event_removes_row(
        self, mock_verify, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        # Seed an installation
        seeded_db.add(
            GitHubInstallation(
                installation_id=57000, account_login="gone", account_id=300
            )
        )
        await seeded_db.commit()

        payload = _make_installation_payload(action="deleted", installation_id=57000)
        res = await seeded_client.post(
            "/github/webhooks",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200

        result = await seeded_db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == 57000
            )
        )
        assert result.scalar_one_or_none() is None

    @patch("app.github.router.verify_webhook_signature", return_value=True)
    async def test_installation_repositories_event_upserts(
        self, mock_verify, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        payload = _make_installation_payload(
            action="added",
            installation_id=58000,
            repos=[
                {"id": 1, "full_name": "org/repo1", "name": "repo1"},
                {"id": 2, "full_name": "org/repo2", "name": "repo2"},
            ],
        )
        res = await seeded_client.post(
            "/github/webhooks",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "installation_repositories",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 200

        result = await seeded_db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == 58000
            )
        )
        assert result.scalar_one_or_none() is not None

    @patch("app.github.router.verify_webhook_signature", return_value=False)
    async def test_invalid_signature_rejected(
        self, mock_verify, seeded_client: AsyncClient
    ) -> None:
        res = await seeded_client.post(
            "/github/webhooks",
            content=b'{"action":"created"}',
            headers={
                "X-Hub-Signature-256": "sha256=bad",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 401

    @patch("app.github.router.verify_webhook_signature", return_value=False)
    async def test_missing_signature_rejected(
        self, mock_verify, seeded_client: AsyncClient
    ) -> None:
        res = await seeded_client.post(
            "/github/webhooks",
            content=b'{"action":"created"}',
            headers={
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )
        assert res.status_code == 401
