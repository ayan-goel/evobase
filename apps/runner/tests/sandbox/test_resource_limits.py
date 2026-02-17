"""Tests for subprocess resource limits in Phase 14C.

The resource module is mocked so tests run on any platform (including
macOS where the behaviour of setrlimit differs from Linux).
"""

import sys
from unittest.mock import MagicMock, call, patch

import pytest

from runner.sandbox.limits import apply_resource_limits


class TestApplyResourceLimits:
    def test_sets_memory_limit(self) -> None:
        """RLIMIT_AS must be set to 512 MB."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5  # arbitrary sentinel
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (512 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_sets_cpu_limit(self) -> None:
        """RLIMIT_CPU must be set to 60 seconds."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_CPU,
            (60, mock_resource.RLIM_INFINITY),
        )

    def test_no_op_on_windows(self) -> None:
        """No rlimits should be set when running on Windows."""
        mock_resource = MagicMock()

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "win32"):
                apply_resource_limits()

        mock_resource.setrlimit.assert_not_called()

    def test_does_not_raise_when_setrlimit_fails(self) -> None:
        """A failing setrlimit (e.g., on hardened hosts) must not crash the worker."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1
        mock_resource.error = Exception
        mock_resource.setrlimit.side_effect = Exception("permission denied")

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                # Must not raise
                apply_resource_limits()
