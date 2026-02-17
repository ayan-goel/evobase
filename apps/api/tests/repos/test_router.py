"""Integration tests for repository endpoints."""

import uuid

import pytest

from tests.conftest import STUB_ORG_ID, STUB_REPO_ID


class TestConnectRepo:
    async def test_connect_repo_success(self, seeded_client):
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 999888777,
                "github_full_name": "acme/api-service",
                "org_id": str(STUB_ORG_ID),
                "default_branch": "main",
                "package_manager": "pnpm",
                "install_cmd": "pnpm install",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["github_repo_id"] == 999888777
        assert data["github_full_name"] == "acme/api-service"
        assert data["package_manager"] == "pnpm"
        assert data["id"] is not None

    async def test_connect_repo_without_full_name(self, seeded_client):
        """github_full_name is optional — repos created without it should still work."""
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 111222333,
                "org_id": str(STUB_ORG_ID),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["github_full_name"] is None

    async def test_connect_repo_duplicate_github_id(self, seeded_client):
        """Connecting a repo with an already-used github_repo_id should 409."""
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 123456789,  # Already in seed data
                "org_id": str(STUB_ORG_ID),
            },
        )
        assert response.status_code == 409

    async def test_connect_repo_nonexistent_org(self, seeded_client):
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 111222333,
                "org_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 404

    async def test_connect_repo_missing_fields(self, seeded_client):
        response = await seeded_client.post(
            "/repos/connect",
            json={},
        )
        assert response.status_code == 422


class TestListRepos:
    async def test_list_repos_returns_seeded_repo(self, seeded_client):
        response = await seeded_client.get("/repos")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["repos"][0]["id"] == str(STUB_REPO_ID)

    async def test_list_repos_empty_for_new_user(self, client):
        """With no seed data, the user should see zero repos."""
        response = await client.get("/repos")
        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestGetRepo:
    async def test_get_repo_success(self, seeded_client):
        response = await seeded_client.get(f"/repos/{STUB_REPO_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["package_manager"] == "npm"
        assert data["default_branch"] == "main"

    async def test_get_repo_not_found(self, seeded_client):
        response = await seeded_client.get(f"/repos/{uuid.uuid4()}")
        assert response.status_code == 404
