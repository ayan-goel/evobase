"""Tests for the SSRF URL validator in Phase 14C.

All DNS lookups for private addresses are mocked so tests run offline
and don't depend on external network state.
"""

import socket
from unittest.mock import patch

import pytest

from runner.sandbox.checkout import SandboxError, redact_repo_url, validate_repo_url


# ---------------------------------------------------------------------------
# Helper: mock getaddrinfo to return a specific IP
# ---------------------------------------------------------------------------

def _mock_getaddrinfo(ip: str):
    """Return a mock getaddrinfo that resolves to the given IP."""
    return lambda host, port: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]


# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------

class TestSchemeValidation:
    def test_http_scheme_is_rejected(self) -> None:
        with pytest.raises(SandboxError, match="HTTPS"):
            validate_repo_url("http://github.com/owner/repo")

    def test_git_scheme_is_rejected(self) -> None:
        with pytest.raises(SandboxError, match="HTTPS"):
            validate_repo_url("git://github.com/owner/repo")

    def test_file_scheme_is_rejected(self) -> None:
        with pytest.raises(SandboxError, match="HTTPS"):
            validate_repo_url("file:///etc/passwd")

    def test_ftp_scheme_is_rejected(self) -> None:
        with pytest.raises(SandboxError, match="HTTPS"):
            validate_repo_url("ftp://example.com/repo")

    def test_ssh_scheme_is_rejected(self) -> None:
        with pytest.raises(SandboxError, match="HTTPS"):
            validate_repo_url("ssh://github.com/owner/repo")

    def test_empty_url_is_rejected(self) -> None:
        with pytest.raises(SandboxError):
            validate_repo_url("")


# ---------------------------------------------------------------------------
# Private network detection
# ---------------------------------------------------------------------------

class TestPrivateNetworkDetection:
    def test_loopback_ipv4_is_rejected(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("127.0.0.1")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://localhost/repo")

    def test_loopback_alternate_is_rejected(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("127.0.0.2")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://internal.host/repo")

    def test_rfc1918_10_network_is_rejected(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("10.0.0.1")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://internal.host/repo")

    def test_rfc1918_172_network_is_rejected(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("172.16.0.1")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://internal.host/repo")

    def test_rfc1918_192_168_network_is_rejected(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("192.168.1.1")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://internal.host/repo")

    def test_aws_metadata_endpoint_is_rejected(self) -> None:
        """169.254.169.254 is the AWS EC2 instance metadata service — must be blocked."""
        with patch("socket.getaddrinfo", _mock_getaddrinfo("169.254.169.254")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://metadata.internal/repo")

    def test_link_local_other_is_rejected(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("169.254.0.1")):
            with pytest.raises(SandboxError, match="SSRF"):
                validate_repo_url("https://some.host/repo")


# ---------------------------------------------------------------------------
# Valid public URLs
# ---------------------------------------------------------------------------

class TestValidPublicUrls:
    def test_github_com_is_accepted(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("140.82.112.3")):
            # Should not raise
            validate_repo_url("https://github.com/owner/repo")

    def test_gitlab_com_is_accepted(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("172.65.251.78")):
            validate_repo_url("https://gitlab.com/owner/repo")

    def test_any_public_ip_is_accepted(self) -> None:
        with patch("socket.getaddrinfo", _mock_getaddrinfo("8.8.8.8")):
            validate_repo_url("https://some-public-git-host.com/repo")


# ---------------------------------------------------------------------------
# DNS resolution failure
# ---------------------------------------------------------------------------

class TestDnsFailure:
    def test_unresolvable_hostname_raises_sandbox_error(self) -> None:
        def fail_resolution(host, port):
            raise socket.gaierror("Name or service not known")

        with patch("socket.getaddrinfo", fail_resolution):
            with pytest.raises(SandboxError, match="resolve"):
                validate_repo_url("https://does-not-exist.invalid/repo")


class TestRepoUrlRedaction:
    def test_masks_password_in_tokenized_url(self) -> None:
        url = "https://x-access-token:ghs_super_secret_token@github.com/acme/repo.git"
        redacted = redact_repo_url(url)
        assert "ghs_super_secret_token" not in redacted
        assert redacted == "https://x-access-token:***@github.com/acme/repo.git"

    def test_masks_username_when_no_password_present(self) -> None:
        url = "https://ghs_super_secret_token@github.com/acme/repo.git"
        redacted = redact_repo_url(url)
        assert "ghs_super_secret_token" not in redacted
        assert redacted == "https://***@github.com/acme/repo.git"

    def test_url_without_credentials_is_unchanged(self) -> None:
        url = "https://github.com/acme/repo.git"
        assert redact_repo_url(url) == url
