"""Tests for GitHub installations management endpoints.

GET /github/installations — list user's installations
GET /github/installations/{id}/repos — list repos for an installation
POST /github/link-installation — link installation to user
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GitHubInstallation
from tests.conftest import STUB_USER_ID, _make_jwt


class TestListInstallations:
    async def test_returns_users_installations(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        seeded_db.add(
            GitHubInstallation(
                installation_id=70000,
                account_login="myorg",
                account_id=500,
                user_id=STUB_USER_ID,
            )
        )
        await seeded_db.commit()

        res = await seeded_client.get("/github/installations")
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 1
        assert data["installations"][0]["installation_id"] == 70000
        assert data["installations"][0]["account_login"] == "myorg"

    async def test_excludes_other_users(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        other_user_id = uuid.uuid4()
        seeded_db.add(
            GitHubInstallation(
                installation_id=71000,
                account_login="otherorg",
                account_id=600,
                user_id=other_user_id,
            )
        )
        await seeded_db.commit()

        res = await seeded_client.get("/github/installations")
        assert res.status_code == 200
        assert res.json()["count"] == 0

    async def test_empty_when_no_installations(
        self, seeded_client: AsyncClient
    ) -> None:
        res = await seeded_client.get("/github/installations")
        assert res.status_code == 200
        assert res.json()["count"] == 0

    async def test_unauthorized_without_auth(
        self, unauthed_client: AsyncClient
    ) -> None:
        res = await unauthed_client.get("/github/installations")
        assert res.status_code == 401


class TestGetInstallationRepos:
    @patch("app.github.client.list_installation_repos", new_callable=AsyncMock)
    @patch("app.github.client.get_installation_token", new_callable=AsyncMock)
    async def test_calls_github_api(
        self,
        mock_token,
        mock_list_repos,
        seeded_client: AsyncClient,
        seeded_db: AsyncSession,
    ) -> None:
        mock_token.return_value = "ghs_fake_token"
        mock_list_repos.return_value = [
            {
                "id": 101,
                "full_name": "testorg/repo1",
                "name": "repo1",
                "default_branch": "main",
                "private": False,
            },
            {
                "id": 102,
                "full_name": "testorg/repo2",
                "name": "repo2",
                "default_branch": "develop",
                "private": True,
            },
        ]

        seeded_db.add(
            GitHubInstallation(
                installation_id=72000,
                account_login="testorg",
                account_id=700,
                user_id=STUB_USER_ID,
            )
        )
        await seeded_db.commit()

        res = await seeded_client.get("/github/installations/72000/repos")

        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 2
        assert data["repos"][0]["full_name"] == "testorg/repo1"
        assert data["repos"][1]["private"] is True
        mock_token.assert_called_once_with(72000)
        mock_list_repos.assert_called_once_with("ghs_fake_token")

    async def test_not_found_for_other_users_installation(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        seeded_db.add(
            GitHubInstallation(
                installation_id=73000,
                account_login="other",
                account_id=800,
                user_id=uuid.uuid4(),
            )
        )
        await seeded_db.commit()

        res = await seeded_client.get("/github/installations/73000/repos")
        assert res.status_code == 404


class TestLinkInstallation:
    async def test_links_existing_installation(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        seeded_db.add(
            GitHubInstallation(
                installation_id=74000,
                account_login="linkorg",
                account_id=900,
            )
        )
        await seeded_db.commit()

        res = await seeded_client.post(
            "/github/link-installation",
            json={"installation_id": 74000},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["linked"] is True
        assert data["installation_id"] == 74000

    async def test_creates_and_links_new_installation(
        self, seeded_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        res = await seeded_client.post(
            "/github/link-installation",
            json={
                "installation_id": 75000,
                "account_login": "neworg",
                "account_id": 1000,
            },
        )
        assert res.status_code == 200
        assert res.json()["linked"] is True

        from sqlalchemy import select
        from app.db.models import GitHubInstallation

        result = await seeded_db.execute(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == 75000
            )
        )
        inst = result.scalar_one_or_none()
        assert inst is not None
        assert inst.user_id == STUB_USER_ID

    async def test_unauthorized_without_auth(
        self, unauthed_client: AsyncClient
    ) -> None:
        res = await unauthed_client.post(
            "/github/link-installation",
            json={"installation_id": 76000},
        )
        assert res.status_code == 401
