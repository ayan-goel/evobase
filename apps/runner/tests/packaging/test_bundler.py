"""Unit tests for the artifact bundler."""

import json

import pytest

from runner.packaging.bundler import bundle_artifacts
from runner.validator.types import BaselineResult, StepResult


@pytest.fixture
def sample_result():
    return BaselineResult(
        steps=[
            StepResult(
                name="install", command="npm ci", exit_code=0,
                duration_seconds=5.0, stdout="added 200 packages",
            ),
            StepResult(
                name="build", command="npm run build", exit_code=0,
                duration_seconds=12.0, stdout="Build complete",
            ),
            StepResult(
                name="test", command="npm test", exit_code=0,
                duration_seconds=8.5, stdout="Tests: 42 passed",
                stderr="Coverage: 95%",
            ),
        ],
        is_success=True,
    )


class TestBundleArtifacts:
    def test_produces_three_artifacts(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        assert len(bundles) == 3

    def test_artifact_filenames(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        filenames = {b.filename for b in bundles}
        assert filenames == {"baseline.json", "logs.txt", "trace.json"}

    def test_storage_paths_follow_convention(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        for bundle in bundles:
            assert bundle.storage_path.startswith("repos/repo-456/runs/run-123/")

    def test_baseline_json_is_valid(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        baseline_bundle = next(b for b in bundles if b.filename == "baseline.json")
        data = json.loads(baseline_bundle.content)

        assert data["is_success"] is True
        assert len(data["steps"]) == 3
        assert data["total_duration_seconds"] == 25.5

    def test_logs_contain_step_output(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        logs_bundle = next(b for b in bundles if b.filename == "logs.txt")

        assert "install" in logs_bundle.content
        assert "npm ci" in logs_bundle.content
        assert "added 200 packages" in logs_bundle.content
        assert "Tests: 42 passed" in logs_bundle.content

    def test_logs_contain_stderr(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        logs_bundle = next(b for b in bundles if b.filename == "logs.txt")

        assert "Coverage: 95%" in logs_bundle.content

    def test_trace_json_is_valid(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        trace_bundle = next(b for b in bundles if b.filename == "trace.json")
        data = json.loads(trace_bundle.content)

        assert data["run_id"] == "run-123"
        assert data["repo_id"] == "repo-456"
        assert data["pipeline"]["is_success"] is True
        assert data["pipeline"]["step_count"] == 3
        assert len(data["steps"]) == 3

    def test_trace_truncates_long_output(self):
        result = BaselineResult(
            steps=[
                StepResult(
                    name="test", command="npm test", exit_code=0,
                    duration_seconds=10.0,
                    stdout="x" * 1000,
                ),
            ],
            is_success=True,
        )
        bundles = bundle_artifacts("run-1", "repo-1", result)
        trace_bundle = next(b for b in bundles if b.filename == "trace.json")
        data = json.loads(trace_bundle.content)

        # Trace preview should be truncated to 500 chars
        assert len(data["steps"][0]["stdout_preview"]) == 500

    def test_artifact_types_are_correct(self, sample_result):
        bundles = bundle_artifacts("run-123", "repo-456", sample_result)
        type_map = {b.filename: b.artifact_type for b in bundles}
        assert type_map["baseline.json"] == "baseline"
        assert type_map["logs.txt"] == "log"
        assert type_map["trace.json"] == "trace"

    def test_failed_pipeline_includes_error_in_logs(self):
        result = BaselineResult(
            steps=[
                StepResult(
                    name="install", command="npm ci", exit_code=1,
                    duration_seconds=2.0, stderr="npm ERR! ERESOLVE",
                ),
            ],
            is_success=False,
            error="Step 'install' failed with exit code 1",
        )
        bundles = bundle_artifacts("run-fail", "repo-1", result)
        logs_bundle = next(b for b in bundles if b.filename == "logs.txt")

        assert "PIPELINE ERROR" in logs_bundle.content
        assert "install" in logs_bundle.content

    def test_empty_result(self):
        result = BaselineResult()
        bundles = bundle_artifacts("run-empty", "repo-1", result)
        assert len(bundles) == 3

        baseline_bundle = next(b for b in bundles if b.filename == "baseline.json")
        data = json.loads(baseline_bundle.content)
        assert data["steps"] == []
        assert data["total_duration_seconds"] == 0.0
