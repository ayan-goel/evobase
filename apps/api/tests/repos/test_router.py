"""Integration tests for repository endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import STUB_ORG_ID, STUB_REPO_ID, _make_jwt


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

    async def test_connect_repo_duplicate_github_id_same_root_dir_conflicts(self, seeded_client):
        """Connecting the same github_repo_id with the same root_dir (both None) is a 409."""
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 123456789,  # Already in seed data (root_dir=None)
                "org_id": str(STUB_ORG_ID),
            },
        )
        assert response.status_code == 409

    async def test_connect_repo_same_github_id_different_root_dir_succeeds(self, seeded_client):
        """Same github_repo_id but a different root_dir should be allowed."""
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 123456789,  # Already in seed data at root (None)
                "org_id": str(STUB_ORG_ID),
                "root_dir": "apps/web",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["github_repo_id"] == 123456789
        assert data["root_dir"] == "apps/web"

    async def test_connect_repo_two_subdirs_of_same_repo_both_succeed(self, seeded_client):
        """Connecting apps/web and apps/api from the same repo are independent connections."""
        r1 = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 777888999,
                "github_full_name": "org/monorepo",
                "org_id": str(STUB_ORG_ID),
                "root_dir": "apps/web",
            },
        )
        assert r1.status_code == 201

        r2 = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 777888999,
                "github_full_name": "org/monorepo",
                "org_id": str(STUB_ORG_ID),
                "root_dir": "apps/api",
            },
        )
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    async def test_connect_repo_duplicate_subdir_conflicts(self, seeded_client):
        """Connecting the exact same repo + root_dir combination twice is a 409."""
        await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 555444333,
                "org_id": str(STUB_ORG_ID),
                "root_dir": "packages/core",
            },
        )
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 555444333,
                "org_id": str(STUB_ORG_ID),
                "root_dir": "packages/core",
            },
        )
        assert response.status_code == 409

    async def test_connect_repo_root_dir_whitespace_normalised(self, seeded_client):
        """root_dir values that are blank after stripping are treated as None (root)."""
        # Connect with an actual root_dir first
        r1 = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 666777888,
                "org_id": str(STUB_ORG_ID),
                "root_dir": "  ",  # blank after strip → treated as root
            },
        )
        assert r1.status_code == 201
        assert r1.json()["root_dir"] is None

        # A second request with no root_dir (also root) should conflict
        r2 = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 666777888,
                "org_id": str(STUB_ORG_ID),
            },
        )
        assert r2.status_code == 409

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

    async def test_connect_repo_with_installation_id(self, seeded_client):
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 444555666,
                "github_full_name": "acme/with-install",
                "org_id": str(STUB_ORG_ID),
                "installation_id": 99000,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["installation_id"] == 99000

    async def test_connect_repo_without_installation_id_still_works(self, seeded_client):
        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 444555667,
                "org_id": str(STUB_ORG_ID),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["installation_id"] is None

    async def test_connect_repo_creates_default_settings(self, seeded_client, seeded_db):
        from sqlalchemy import select
        from app.db.models import Settings

        response = await seeded_client.post(
            "/repos/connect",
            json={
                "github_repo_id": 444555668,
                "org_id": str(STUB_ORG_ID),
            },
        )
        assert response.status_code == 201
        repo_id = response.json()["id"]

        result = await seeded_db.execute(
            select(Settings).where(Settings.repo_id == uuid.UUID(repo_id))
        )
        settings = result.scalar_one_or_none()
        assert settings is not None
        assert settings.compute_budget_minutes == 60


class TestListRepos:
    async def test_list_repos_returns_seeded_repo(self, seeded_client):
        response = await seeded_client.get("/repos")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["repos"][0]["id"] == str(STUB_REPO_ID)

    async def test_list_repos_empty_for_new_user(self, app, db_session):
        """A fresh user with no repos should see zero repos."""
        new_user_id = uuid.uuid4()
        token = _make_jwt(sub=new_user_id, email="fresh@example.com")
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            response = await ac.get("/repos")
            assert response.status_code == 200
            assert response.json()["count"] == 0

    async def test_list_repos_latest_run_status_null_when_no_runs(self, seeded_client):
        """Repo with no runs has latest_run_status: null."""
        response = await seeded_client.get("/repos")
        assert response.status_code == 200
        repo_data = response.json()["repos"][0]
        assert repo_data["latest_run_status"] is None
        assert repo_data["latest_failure_step"] is None

    async def test_list_repos_includes_latest_run_status(self, seeded_client, seeded_db):
        """Repo with a completed run reports latest_run_status correctly."""
        from app.db.models import Run

        run = Run(
            repo_id=STUB_REPO_ID,
            sha="abc123",
            status="completed",
            failure_step="test",
        )
        seeded_db.add(run)
        await seeded_db.commit()

        response = await seeded_client.get("/repos")
        assert response.status_code == 200
        repo_data = response.json()["repos"][0]
        assert repo_data["latest_run_status"] == "completed"
        assert repo_data["latest_failure_step"] == "test"


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

    async def test_get_repo_includes_latest_run_status(self, seeded_client, seeded_db):
        """Single-repo GET returns latest_run_status, null when no runs."""
        response = await seeded_client.get(f"/repos/{STUB_REPO_ID}")
        assert response.status_code == 200
        assert response.json()["latest_run_status"] is None
        assert response.json()["latest_failure_step"] is None

        # Seed a running run and check the status updates
        from app.db.models import Run

        run = Run(
            repo_id=STUB_REPO_ID,
            sha="def456",
            status="running",
            failure_step="install",
        )
        seeded_db.add(run)
        await seeded_db.commit()

        response = await seeded_client.get(f"/repos/{STUB_REPO_ID}")
        assert response.status_code == 200
        assert response.json()["latest_run_status"] == "running"
        assert response.json()["latest_failure_step"] == "install"
