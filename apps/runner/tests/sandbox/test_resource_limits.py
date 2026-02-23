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
        """Default profile RLIMIT_AS must be set to 4 GB.

        512 MB was too low — Node.js / V8 maps several GB of virtual address
        space at startup, causing SIGTRAP (exit 133) before npm can run.
        """
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5  # arbitrary sentinel
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (4 * 1024 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_js_profile_skips_rlimit_as(self) -> None:
        """JS profile disables RLIMIT_AS to avoid blocking Wasm virtual mappings.

        WebAssembly (Turbopack/SWC/Vitest) requires large contiguous virtual
        address space blocks that trip a per-process RLIMIT_AS cap even on
        machines with plenty of physical RAM. The JS profile therefore leaves
        virtual address space unlimited and bounds memory via NODE_OPTIONS
        instead.
        """
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict("os.environ", {"CORELOOP_RESOURCE_PROFILE": "js"}, clear=False):
                    apply_resource_limits()

        # RLIMIT_AS must NOT be set for the JS profile.
        for call_args in mock_resource.setrlimit.call_args_list:
            assert call_args[0][0] != mock_resource.RLIMIT_AS, (
                "RLIMIT_AS should not be set for the JS resource profile"
            )

    def test_sets_jvm_memory_limit_when_profile_is_jvm(self) -> None:
        """JVM profile uses a higher RLIMIT_AS default (12 GB)."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict("os.environ", {"CORELOOP_RESOURCE_PROFILE": "jvm"}, clear=False):
                    apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (12 * 1024 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_sets_native_memory_limit_when_profile_is_native(self) -> None:
        """Native profile uses a higher RLIMIT_AS default (16 GB)."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict("os.environ", {"CORELOOP_RESOURCE_PROFILE": "native"}, clear=False):
                    apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (16 * 1024 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_memory_limit_can_be_overridden_by_env(self) -> None:
        """RLIMIT_AS uses explicit env override when set."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict("os.environ", {"CORELOOP_RLIMIT_AS_BYTES": str(8 * 1024 * 1024 * 1024)}, clear=False):
                    apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (8 * 1024 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_jvm_memory_limit_can_be_overridden_by_env(self) -> None:
        """JVM profile honors JVM-specific memory override env."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict(
                    "os.environ",
                    {
                        "CORELOOP_RESOURCE_PROFILE": "jvm",
                        "CORELOOP_RLIMIT_AS_BYTES_JVM": str(10 * 1024 * 1024 * 1024),
                    },
                    clear=False,
                ):
                    apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (10 * 1024 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_native_memory_limit_can_be_overridden_by_env(self) -> None:
        """Native profile honors native-specific memory override env."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict(
                    "os.environ",
                    {
                        "CORELOOP_RESOURCE_PROFILE": "native",
                        "CORELOOP_RLIMIT_AS_BYTES_NATIVE": str(14 * 1024 * 1024 * 1024),
                    },
                    clear=False,
                ):
                    apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_AS,
            (14 * 1024 * 1024 * 1024, mock_resource.RLIM_INFINITY),
        )

    def test_memory_limit_can_be_disabled_with_zero_override(self) -> None:
        """Setting CORELOOP_RLIMIT_AS_BYTES=0 disables RLIMIT_AS."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict("os.environ", {"CORELOOP_RLIMIT_AS_BYTES": "0"}, clear=False):
                    apply_resource_limits()

        as_calls = [
            c for c in mock_resource.setrlimit.call_args_list
            if c.args and c.args[0] == mock_resource.RLIMIT_AS
        ]
        assert not as_calls
        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_CPU,
            (300, mock_resource.RLIM_INFINITY),
        )

    def test_sets_cpu_limit(self) -> None:
        """RLIMIT_CPU must be set to 300 seconds (matches wall-clock timeout)."""
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_CPU,
            (300, mock_resource.RLIM_INFINITY),
        )

    def test_cpu_limit_can_be_overridden_by_env(self) -> None:
        mock_resource = MagicMock()
        mock_resource.RLIMIT_AS = 5
        mock_resource.RLIMIT_CPU = 0
        mock_resource.RLIM_INFINITY = -1

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                with patch.dict("os.environ", {"CORELOOP_RLIMIT_CPU_SECONDS": "450"}, clear=False):
                    apply_resource_limits()

        mock_resource.setrlimit.assert_any_call(
            mock_resource.RLIMIT_CPU,
            (450, mock_resource.RLIM_INFINITY),
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
        mock_resource.setrlimit.side_effect = OSError("permission denied")

        with patch.dict("sys.modules", {"resource": mock_resource}):
            with patch("sys.platform", "linux"):
                # Must not raise
                apply_resource_limits()
