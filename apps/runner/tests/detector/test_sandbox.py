"""Tests for the sandbox checkout module.

Tests clone and checkout logic using subprocess mocks.
Actual git operations are not performed in unit tests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runner.sandbox.checkout import checkout_sha, clone_repo


class TestCloneRepo:
    @patch("runner.sandbox.checkout.subprocess.run")
    def test_clone_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = clone_repo("https://github.com/user/repo.git", tmp_path)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "git" in cmd
        assert "clone" in cmd
        assert result == tmp_path

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_clone_failure_raises(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=128, stderr="fatal: repository not found"
        )

        with pytest.raises(RuntimeError, match="git clone failed"):
            clone_repo("https://github.com/user/nonexistent.git", tmp_path)

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_clone_shallow_by_default(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        clone_repo("https://github.com/user/repo.git", tmp_path)

        cmd = mock_run.call_args[0][0]
        assert "--depth" in cmd
        assert "1" in cmd

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_clone_creates_temp_dir_if_none(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        result = clone_repo("https://github.com/user/repo.git")

        assert result is not None
        assert "coreloop-" in str(result)

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_clone_custom_depth(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        clone_repo("https://github.com/user/repo.git", tmp_path, depth=10)

        cmd = mock_run.call_args[0][0]
        assert "10" in cmd


class TestCheckoutSha:
    @patch("runner.sandbox.checkout.subprocess.run")
    def test_checkout_success(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        checkout_sha(tmp_path, "abc123")

        assert mock_run.call_count == 2  # fetch + checkout

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_checkout_fetch_failure_raises(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(
            returncode=128, stderr="fatal: couldn't find remote ref"
        )

        with pytest.raises(RuntimeError, match="git fetch failed"):
            checkout_sha(tmp_path, "nonexistent-sha")

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_checkout_failure_raises(self, mock_run, tmp_path):
        # First call (fetch) succeeds, second (checkout) fails
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr=""),
            MagicMock(returncode=1, stderr="error: pathspec did not match"),
        ]

        with pytest.raises(RuntimeError, match="git checkout failed"):
            checkout_sha(tmp_path, "bad-sha")

    @patch("runner.sandbox.checkout.subprocess.run")
    def test_checkout_passes_sha_to_git(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        checkout_sha(tmp_path, "abc123def456")

        # The fetch command should include the SHA
        fetch_cmd = mock_run.call_args_list[0][0][0]
        assert "abc123def456" in fetch_cmd

        # The checkout command should include the SHA
        checkout_cmd = mock_run.call_args_list[1][0][0]
        assert "abc123def456" in checkout_cmd
