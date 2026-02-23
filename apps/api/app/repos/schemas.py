"""Pydantic schemas for repository endpoints.

Follows RORO pattern: receive a typed object, return a typed object.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class RepoConnectRequest(BaseModel):
    """Payload for connecting a new GitHub repository."""

    github_repo_id: int = Field(..., description="GitHub repository numeric ID")
    github_full_name: Optional[str] = Field(
        default=None,
        description="GitHub 'owner/repo' full name, e.g. 'acme/api-service'",
    )
    org_id: uuid.UUID = Field(..., description="Organization to attach this repo to")
    default_branch: str = Field(default="main")
    installation_id: Optional[int] = Field(
        default=None,
        description="GitHub App installation ID (from github_installations table)",
    )
    package_manager: Optional[str] = None
    install_cmd: Optional[str] = None
    build_cmd: Optional[str] = None
    test_cmd: Optional[str] = None
    typecheck_cmd: Optional[str] = None
    bench_config: Optional[dict[str, Any]] = None
    root_dir: Optional[str] = Field(
        default=None,
        description="Subdirectory to use as the project root (for monorepos).",
    )


class RepoPatchRequest(BaseModel):
    """Payload for updating mutable repository configuration fields."""

    root_dir: Optional[str] = Field(
        default=None,
        description="Subdirectory to use as the project root (for monorepos). "
        "Pass an empty string to clear a previously set value.",
    )
    install_cmd: Optional[str] = None
    build_cmd: Optional[str] = None
    test_cmd: Optional[str] = None
    typecheck_cmd: Optional[str] = None


class RepoResponse(BaseModel):
    """Response schema for a single repository."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    org_id: uuid.UUID
    github_repo_id: Optional[int]
    github_full_name: Optional[str] = None
    default_branch: str
    installation_id: Optional[int] = None
    package_manager: Optional[str]
    framework: Optional[str] = None
    install_cmd: Optional[str]
    build_cmd: Optional[str]
    test_cmd: Optional[str]
    typecheck_cmd: Optional[str] = None
    bench_config: Optional[dict[str, Any]]
    root_dir: Optional[str] = None
    latest_run_status: Optional[str] = None
    latest_failure_step: Optional[str] = None
    # True when consecutive_setup_failures > 0 for this repo's settings row.
    setup_failing: bool = False
    created_at: datetime


class RepoConnectResponse(RepoResponse):
    """Response schema for POST /repos/connect — includes the auto-created run ID."""

    initial_run_id: Optional[str] = None


class RepoListResponse(BaseModel):
    """Paginated list of repositories."""

    repos: list[RepoResponse]
    count: int


class DetectFrameworkRequest(BaseModel):
    """Payload for the lightweight framework detection endpoint."""

    installation_id: int = Field(..., description="GitHub App installation ID")
    repo_full_name: str = Field(..., description="'owner/repo' full name")
    root_dir: Optional[str] = Field(
        default=None,
        description="Subdirectory to probe (for monorepos). Omit to probe the repo root.",
    )


class DetectFrameworkResponse(BaseModel):
    """Detected framework metadata — informational only (no commands)."""

    framework: Optional[str] = None
    language: Optional[str] = None
    package_manager: Optional[str] = None
    confidence: float = 0.0
