"""Unit tests for repository Pydantic schemas."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.repos.schemas import RepoConnectRequest, RepoListResponse, RepoResponse


class TestRepoConnectRequest:
    def test_valid_minimal_request(self):
        req = RepoConnectRequest(
            github_repo_id=123,
            org_id=uuid.uuid4(),
        )
        assert req.default_branch == "main"
        assert req.package_manager is None

    def test_valid_full_request(self):
        req = RepoConnectRequest(
            github_repo_id=456,
            org_id=uuid.uuid4(),
            default_branch="develop",
            package_manager="pnpm",
            install_cmd="pnpm install",
            build_cmd="pnpm build",
            test_cmd="pnpm test",
            bench_config={"mode": "http", "url": "/api/health"},
        )
        assert req.package_manager == "pnpm"
        assert req.bench_config["mode"] == "http"

    def test_missing_required_fields_raises(self):
        with pytest.raises(ValidationError):
            RepoConnectRequest()

    def test_missing_org_id_raises(self):
        with pytest.raises(ValidationError):
            RepoConnectRequest(github_repo_id=123)


class TestRepoResponse:
    def test_from_attributes(self):
        """Verify the schema can construct from ORM-like objects."""
        data = {
            "id": uuid.uuid4(),
            "org_id": uuid.uuid4(),
            "github_repo_id": 999,
            "default_branch": "main",
            "package_manager": "npm",
            "install_cmd": "npm install",
            "build_cmd": None,
            "test_cmd": "npm test",
            "bench_config": None,
            "created_at": datetime.now(),
        }
        resp = RepoResponse(**data)
        assert resp.github_repo_id == 999


class TestRepoListResponse:
    def test_empty_list(self):
        resp = RepoListResponse(repos=[], count=0)
        assert resp.count == 0
        assert resp.repos == []
