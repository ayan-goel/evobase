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

Limits chosen:
  RLIMIT_AS (virtual address space): 4 GB
    Prevents a subprocess from allocating unbounded memory. Node.js / V8
    maps several GB of virtual address space at startup (for the isolate
    heap cage) even though physical pages are only committed on demand.
    512 MB trips this limit before npm can execute a single line, causing
    SIGTRAP (exit 133). 4 GB is a safe ceiling that blocks truly runaway
    processes while allowing all typical install/build/test workloads.

  RLIMIT_CPU (CPU seconds): 60 seconds
    Prevents infinite CPU loops from consuming the entire worker core.
    This is wall-CPU time, not wall-clock time — a well-behaved process
    that sleeps won't be killed prematurely.
"""

import sys
from typing import Optional


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

        # 4 GB virtual address space hard limit — Node.js / V8 maps several GB
        # of virtual space at startup even for lightweight tasks, so anything
        # below ~2 GB causes an immediate SIGTRAP before npm can run.
        _MEM_LIMIT = 4 * 1024 * 1024 * 1024  # 4 GB
        resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT, resource.RLIM_INFINITY))

        # 60 CPU-seconds hard limit (separate from wall-clock timeout)
        _CPU_LIMIT = 60
        resource.setrlimit(resource.RLIMIT_CPU, (_CPU_LIMIT, resource.RLIM_INFINITY))

    except (ImportError, ValueError, resource.error) as exc:
        # Log but don't raise — a failed rlimit shouldn't abort the pipeline.
        # The wall-clock timeout is still in effect.
        import logging
        logging.getLogger(__name__).warning(
            "Failed to apply resource limits: %s", exc
        )
