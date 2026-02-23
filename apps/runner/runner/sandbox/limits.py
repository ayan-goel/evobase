"""Subprocess resource limits for sandboxed execution.

Provides a `preexec_fn`-compatible function that sets hard resource
limits on child processes before exec. This is a defence-in-depth
measure — the wall-clock timeout in subprocess.run() is the primary
guard, but rlimits prevent runaway CPU usage and memory exhaustion
even if the wall-clock guard is bypassed (e.g., a process that sleeps
between CPU bursts).

Platform notes:
  - Linux / macOS: `resource` module is available and rlimits are enforced.
  - Windows: `resource` module is unavailable. `apply_resource_limits()`
    is a no-op on Windows so tests and development on Windows are unaffected.

Memory policy:
  - Default profile: 4 GB virtual-address-space cap (`RLIMIT_AS`).
  - JS profile: 12 GB virtual-address-space cap by default.
    Node + Wasm-heavy workloads (Next.js builds / Vitest) can exceed 4 GB of
    *virtual* mappings even when physical memory is available.
  - JVM profile: 12 GB virtual-address-space cap by default.
    Gradle/Maven builds can start multiple JVMs and require larger virtual
    address mappings than the default profile.
  - Native profile: 16 GB virtual-address-space cap by default.
    Rust and C/C++ linker-heavy builds can use large address-space mappings
    during compile/link phases.

Environment overrides:
  - CORELOOP_RESOURCE_PROFILE: "default" | "js" | "jvm" | "native"
  - CORELOOP_RLIMIT_AS_BYTES: integer bytes for default profile
  - CORELOOP_RLIMIT_AS_BYTES_JS: integer bytes for js profile
  - CORELOOP_RLIMIT_AS_BYTES_JVM: integer bytes for jvm profile
  - CORELOOP_RLIMIT_AS_BYTES_NATIVE: integer bytes for native profile
  - CORELOOP_RLIMIT_CPU_SECONDS: integer seconds for CPU limit

If either memory env value is set to 0 or negative, RLIMIT_AS is skipped for
that profile. This is useful on high-memory dedicated workers.
"""

import os
import sys
from typing import Optional

# Default memory caps
_DEFAULT_MEM_LIMIT_BYTES = 4 * 1024 * 1024 * 1024   # 4 GB
_DEFAULT_JS_MEM_LIMIT_BYTES = 12 * 1024 * 1024 * 1024  # 12 GB
_DEFAULT_JVM_MEM_LIMIT_BYTES = 12 * 1024 * 1024 * 1024  # 12 GB
_DEFAULT_NATIVE_MEM_LIMIT_BYTES = 16 * 1024 * 1024 * 1024  # 16 GB
_DEFAULT_CPU_LIMIT_SECONDS = 300

# Environment overrides
_RESOURCE_PROFILE_ENV = "CORELOOP_RESOURCE_PROFILE"
_MEM_LIMIT_ENV = "CORELOOP_RLIMIT_AS_BYTES"
_JS_MEM_LIMIT_ENV = "CORELOOP_RLIMIT_AS_BYTES_JS"
_JVM_MEM_LIMIT_ENV = "CORELOOP_RLIMIT_AS_BYTES_JVM"
_NATIVE_MEM_LIMIT_ENV = "CORELOOP_RLIMIT_AS_BYTES_NATIVE"
_CPU_LIMIT_ENV = "CORELOOP_RLIMIT_CPU_SECONDS"


def _parse_optional_positive_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    value = int(raw.strip())
    if value <= 0:
        return 0
    return value


def _resolve_memory_limit_bytes() -> Optional[int]:
    profile = os.environ.get(_RESOURCE_PROFILE_ENV, "default").strip().lower()

    if profile == "js":
        js_override = _parse_optional_positive_int(os.environ.get(_JS_MEM_LIMIT_ENV))
        if js_override is not None:
            return js_override
        base_override = _parse_optional_positive_int(os.environ.get(_MEM_LIMIT_ENV))
        if base_override is not None:
            return base_override
        return _DEFAULT_JS_MEM_LIMIT_BYTES

    if profile == "jvm":
        jvm_override = _parse_optional_positive_int(os.environ.get(_JVM_MEM_LIMIT_ENV))
        if jvm_override is not None:
            return jvm_override
        base_override = _parse_optional_positive_int(os.environ.get(_MEM_LIMIT_ENV))
        if base_override is not None:
            return base_override
        return _DEFAULT_JVM_MEM_LIMIT_BYTES

    if profile == "native":
        native_override = _parse_optional_positive_int(os.environ.get(_NATIVE_MEM_LIMIT_ENV))
        if native_override is not None:
            return native_override
        base_override = _parse_optional_positive_int(os.environ.get(_MEM_LIMIT_ENV))
        if base_override is not None:
            return base_override
        return _DEFAULT_NATIVE_MEM_LIMIT_BYTES

    base_override = _parse_optional_positive_int(os.environ.get(_MEM_LIMIT_ENV))
    if base_override is not None:
        return base_override
    return _DEFAULT_MEM_LIMIT_BYTES


def _resolve_cpu_limit_seconds() -> int:
    raw = os.environ.get(_CPU_LIMIT_ENV)
    if not raw:
        return _DEFAULT_CPU_LIMIT_SECONDS
    parsed = int(raw.strip())
    if parsed <= 0:
        return _DEFAULT_CPU_LIMIT_SECONDS
    return parsed


def apply_resource_limits() -> None:
    """Set per-process resource limits before exec. No-op on Windows.

    Designed to be passed as `preexec_fn` to `subprocess.run()` or
    `subprocess.Popen()`. Executes in the child process context after
    `fork()` but before `exec()`.

    Usage:
        subprocess.run(cmd, preexec_fn=apply_resource_limits, ...)
    """
    if sys.platform == "win32":
        return

    try:
        import resource

        profile = os.environ.get(_RESOURCE_PROFILE_ENV, "default").strip().lower()
        mem_limit = _resolve_memory_limit_bytes()
        if mem_limit and mem_limit > 0:
            resource.setrlimit(resource.RLIMIT_AS, (mem_limit, resource.RLIM_INFINITY))

        cpu_limit = _resolve_cpu_limit_seconds()
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, resource.RLIM_INFINITY))

        import logging
        logging.getLogger(__name__).debug(
            "Resource limits applied: profile=%s mem=%s cpu=%ds",
            profile,
            f"{mem_limit / (1024**3):.1f}GB" if mem_limit else "unlimited",
            cpu_limit,
        )

    except (ImportError, ValueError, OSError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to apply resource limits: %s", exc
        )
