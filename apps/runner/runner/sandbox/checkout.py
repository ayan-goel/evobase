"""Git checkout operations for sandbox execution.

Handles cloning repositories and checking out specific SHAs.
All operations target a temporary workspace directory that is
cleaned up after the run completes.

Security:
  - All repo URLs are validated with validate_repo_url() before any
    subprocess is spawned. This prevents SSRF attacks where a malicious
    repo URL could be used to probe internal network services.
  - All git subprocesses run with apply_resource_limits() as preexec_fn
    to cap memory and CPU usage.
"""

import ipaddress
import logging
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from runner.sandbox.limits import apply_resource_limits

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSRF guard
# ---------------------------------------------------------------------------

# RFC 1918, loopback, link-local, and IPv6 private ranges
_PRIVATE_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback (IPv4)
    ipaddress.ip_network("10.0.0.0/8"),         # RFC 1918 private
    ipaddress.ip_network("172.16.0.0/12"),      # RFC 1918 private
    ipaddress.ip_network("192.168.0.0/16"),     # RFC 1918 private
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local / AWS metadata
    ipaddress.ip_network("100.64.0.0/10"),      # Shared address space (RFC 6598)
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]


class SandboxError(Exception):
    """Raised when a sandbox security check fails."""


def redact_repo_url(url: str) -> str:
    """Return a clone URL safe to write into logs.

    Masks embedded credentials (e.g. installation tokens) while preserving
    host/path context useful for debugging.
    """
    parsed = urlparse(url)
    if parsed.username is None:
        return url

    host = parsed.hostname or ""
    if not host:
        return url

    port = f":{parsed.port}" if parsed.port else ""
    if parsed.password is not None:
        auth = f"{parsed.username}:***@"
    else:
        auth = "***@"

    redacted_netloc = f"{auth}{host}{port}"
    return urlunparse(parsed._replace(netloc=redacted_netloc))


def validate_repo_url(url: str) -> None:
    """Validate a repository URL before cloning.

    Blocks:
      - Non-HTTPS schemes (http://, git://, file://, etc.)
      - Hostnames that resolve to any private, loopback, or link-local IP
        address (SSRF prevention)

    Args:
        url: The repository URL to validate.

    Raises:
        SandboxError: If the URL is invalid or resolves to a private address.
    """
    if not url:
        raise SandboxError("Repository URL must not be empty")

    parsed = urlparse(url)
    safe_url = redact_repo_url(url)

    # Only allow HTTPS
    if parsed.scheme != "https":
        raise SandboxError(
            f"Repository URL must use HTTPS (got scheme '{parsed.scheme}'): {safe_url}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise SandboxError(f"Repository URL has no hostname: {safe_url}")

    # Resolve hostname to IP addresses and check each against private ranges
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SandboxError(
            f"Cannot resolve hostname '{hostname}': {exc}"
        )

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        for private_net in _PRIVATE_NETWORKS:
            if ip in private_net:
                raise SandboxError(
                    f"SSRF: repository hostname '{hostname}' resolves to "
                    f"private address {ip} (network {private_net}): {safe_url}"
                )

    logger.debug("URL validation passed: %s", safe_url)


# ---------------------------------------------------------------------------
# Checkout helpers
# ---------------------------------------------------------------------------


def clone_repo(
    repo_url: str,
    workspace_dir: Path | None = None,
    depth: int = 1,
) -> Path:
    """Clone a repository into a workspace directory.

    Validates the URL against SSRF attacks before cloning.
    Uses shallow clone (depth=1) by default for speed.
    If workspace_dir is None, creates a temporary directory.

    Returns the path to the cloned repo root.
    """
    validate_repo_url(repo_url)

    if workspace_dir is None:
        workspace_dir = Path(tempfile.mkdtemp(prefix="coreloop-"))

    workspace_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", "--depth", str(depth), repo_url, str(workspace_dir)]
    logger.info("Cloning %s into %s", redact_repo_url(repo_url), workspace_dir)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        preexec_fn=apply_resource_limits,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"git clone failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    logger.info("Clone complete: %s", workspace_dir)
    return workspace_dir


def get_head_sha(repo_dir: Path) -> str:
    """Return the full SHA of the current HEAD commit."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=10,
        preexec_fn=apply_resource_limits,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git rev-parse HEAD failed: {result.stderr.strip()}")
    return result.stdout.strip()


def checkout_sha(repo_dir: Path, sha: str) -> None:
    """Checkout a specific commit SHA in the repo.

    Fetches the SHA first (needed for shallow clones),
    then performs a detached HEAD checkout.
    """
    logger.info("Checking out SHA %s in %s", sha, repo_dir)

    # Fetch the specific commit (shallow clones may not have it)
    fetch_result = subprocess.run(
        ["git", "fetch", "origin", sha, "--depth=1"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=120,
        preexec_fn=apply_resource_limits,
    )

    if fetch_result.returncode != 0:
        raise RuntimeError(
            f"git fetch failed for SHA {sha}: {fetch_result.stderr.strip()}"
        )

    # Detached HEAD checkout
    checkout_result = subprocess.run(
        ["git", "checkout", sha],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=60,
        preexec_fn=apply_resource_limits,
    )

    if checkout_result.returncode != 0:
        raise RuntimeError(
            f"git checkout failed for SHA {sha}: {checkout_result.stderr.strip()}"
        )

    logger.info("Checked out %s successfully", sha)
