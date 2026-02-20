"""Unit tests for run Pydantic schemas."""

import uuid
from datetime import datetime

from app.runs.schemas import RUN_STATUSES, RunCreateRequest, RunListResponse, RunResponse


class TestRunCreateRequest:
    def test_default_sha_is_none(self):
        req = RunCreateRequest()
        assert req.sha is None

    def test_explicit_sha(self):
        req = RunCreateRequest(sha="abc123")
        assert req.sha == "abc123"


class TestRunResponse:
    def test_from_dict(self):
        data = {
            "id": uuid.uuid4(),
            "repo_id": uuid.uuid4(),
            "sha": "abc123",
            "status": "queued",
            "compute_minutes": 0,
            "created_at": datetime.now(),
        }
        resp = RunResponse(**data)
        assert resp.status == "queued"

    def test_failure_step_defaults_to_none(self):
        data = {
            "id": uuid.uuid4(),
            "repo_id": uuid.uuid4(),
            "sha": "abc123",
            "status": "completed",
            "compute_minutes": 0,
            "created_at": datetime.now(),
        }
        resp = RunResponse(**data)
        assert resp.failure_step is None

    def test_failure_step_populated(self):
        data = {
            "id": uuid.uuid4(),
            "repo_id": uuid.uuid4(),
            "sha": "abc123",
            "status": "completed",
            "compute_minutes": 0,
            "failure_step": "test",
            "created_at": datetime.now(),
        }
        resp = RunResponse(**data)
        assert resp.failure_step == "test"

    def test_commit_message_defaults_to_none(self):
        data = {
            "id": uuid.uuid4(),
            "repo_id": uuid.uuid4(),
            "sha": "abc123",
            "status": "queued",
            "compute_minutes": 0,
            "created_at": datetime.now(),
        }
        resp = RunResponse(**data)
        assert resp.commit_message is None

    def test_commit_message_populated(self):
        data = {
            "id": uuid.uuid4(),
            "repo_id": uuid.uuid4(),
            "sha": "abc123",
            "status": "completed",
            "compute_minutes": 0,
            "commit_message": "feat: add dark mode",
            "created_at": datetime.now(),
        }
        resp = RunResponse(**data)
        assert resp.commit_message == "feat: add dark mode"


class TestRunStatuses:
    def test_valid_statuses(self):
        assert RUN_STATUSES == {"queued", "running", "completed", "failed"}
