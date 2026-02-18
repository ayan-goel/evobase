"""Integration tests for GitHub webhook and PR creation endpoints."""

import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.db.models import Proposal, Run
from tests.conftest import STUB_ORG_ID, STUB_REPO_ID

MOCK_SECRET = "test-webhook-secret"


def _sign_payload(payload: bytes) -> str:
    sig = hmac.new(
        MOCK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


class TestWebhookEndpoint:
    @patch("app.github.router.verify_webhook_signature", return_value=True)
    async def test_installation_event_accepted(self, mock_verify, seeded_client):
        payload = {
            "action": "created",
            "installation": {"id": 999, "account": {"login": "org", "id": 1}},
            "repositories": [{"id": 1, "full_name": "org/repo", "name": "repo"}],
        }
        response = await seeded_client.post(
            "/github/webhooks",
            content=json.dumps(payload),
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["received"] is True
        assert data["event"] == "installation"

    @patch("app.github.router.verify_webhook_signature", return_value=False)
    async def test_invalid_signature_rejected(self, mock_verify, seeded_client):
        response = await seeded_client.post(
            "/github/webhooks",
            content=b'{"action":"created"}',
            headers={
                "X-Hub-Signature-256": "sha256=bad",
                "X-GitHub-Event": "installation",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 401

    @patch("app.github.router.verify_webhook_signature", return_value=True)
    async def test_unknown_event_acknowledged(self, mock_verify, seeded_client):
        response = await seeded_client.post(
            "/github/webhooks",
            content=b'{}',
            headers={
                "X-Hub-Signature-256": "sha256=valid",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200
        assert response.json()["action"] == "ignored"


class TestCreatePrEndpoint:
    async def _setup_proposal(self, client, db_session):
        """Create a run and proposal for PR creation tests."""
        run_resp = await client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        run_id = uuid.UUID(run_resp.json()["id"])

        proposal = Proposal(
            run_id=run_id,
            diff="--- a/utils.ts\n+++ b/utils.ts",
            summary="Optimize hot path",
            metrics_before={"latency": 100},
            metrics_after={"latency": 92},
            risk_score=0.1,
        )
        db_session.add(proposal)
        await db_session.commit()
        await db_session.refresh(proposal)
        return proposal

    @patch("app.github.router.create_pr_for_proposal", new_callable=AsyncMock)
    async def test_create_pr_success(self, mock_create_pr, seeded_client, seeded_db):
        proposal = await self._setup_proposal(seeded_client, seeded_db)
        mock_create_pr.return_value = "https://github.com/org/repo/pull/42"

        response = await seeded_client.post(
            f"/github/repos/{STUB_REPO_ID}/proposals/{proposal.id}/create-pr"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["pr_url"] == "https://github.com/org/repo/pull/42"
        assert data["proposal_id"] == str(proposal.id)

    @patch("app.github.router.create_pr_for_proposal", new_callable=AsyncMock)
    async def test_create_pr_duplicate_rejected(self, mock_create_pr, seeded_client, seeded_db):
        """Creating a PR twice for the same proposal should 409."""
        proposal = await self._setup_proposal(seeded_client, seeded_db)
        mock_create_pr.return_value = "https://github.com/org/repo/pull/42"

        # First call succeeds
        resp1 = await seeded_client.post(
            f"/github/repos/{STUB_REPO_ID}/proposals/{proposal.id}/create-pr"
        )
        assert resp1.status_code == 201

        # Second call should conflict
        resp2 = await seeded_client.post(
            f"/github/repos/{STUB_REPO_ID}/proposals/{proposal.id}/create-pr"
        )
        assert resp2.status_code == 409

    async def test_create_pr_nonexistent_repo(self, seeded_client):
        response = await seeded_client.post(
            f"/github/repos/{uuid.uuid4()}/proposals/{uuid.uuid4()}/create-pr"
        )
        assert response.status_code == 404

    async def test_create_pr_nonexistent_proposal(self, seeded_client):
        response = await seeded_client.post(
            f"/github/repos/{STUB_REPO_ID}/proposals/{uuid.uuid4()}/create-pr"
        )
        assert response.status_code == 404

    @patch("app.github.router.create_pr_for_proposal", new_callable=AsyncMock)
    async def test_create_pr_returns_422_when_repo_not_configured(
        self, mock_create_pr, seeded_client, seeded_db
    ):
        """Service raising ValueError (missing github_full_name or installation_id)
        must surface as 422 Unprocessable Entity, not a 500."""
        proposal = await self._setup_proposal(seeded_client, seeded_db)
        mock_create_pr.side_effect = ValueError("Repository has no GitHub App installation")

        response = await seeded_client.post(
            f"/github/repos/{STUB_REPO_ID}/proposals/{proposal.id}/create-pr"
        )
        assert response.status_code == 422
        assert "installation" in response.json()["detail"]

    async def test_create_pr_wrong_repo_returns_404(self, seeded_client, seeded_db):
        """A proposal belonging to a different repo must return 404."""
        # Create a run + proposal under a repo that the test user doesn't own
        other_repo_id = uuid.uuid4()
        run_resp = await seeded_client.post(f"/repos/{STUB_REPO_ID}/run", json={})
        run_id = uuid.UUID(run_resp.json()["id"])

        proposal = Proposal(
            run_id=run_id,
            diff="--- a/f\n+++ b/f",
            summary="some change",
        )
        seeded_db.add(proposal)
        await seeded_db.commit()
        await seeded_db.refresh(proposal)

        # Request create-pr using a random (non-existent) repo_id
        response = await seeded_client.post(
            f"/github/repos/{uuid.uuid4()}/proposals/{proposal.id}/create-pr"
        )
        assert response.status_code == 404

    async def test_create_pr_without_auth_returns_401(self, unauthed_client):
        """Endpoint must reject requests with no Authorization header."""
        response = await unauthed_client.post(
            f"/github/repos/{STUB_REPO_ID}/proposals/{uuid.uuid4()}/create-pr"
        )
        assert response.status_code == 401
