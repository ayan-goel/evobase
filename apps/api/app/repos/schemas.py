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
    package_manager: Optional[str] = None
    install_cmd: Optional[str] = None
    build_cmd: Optional[str] = None
    test_cmd: Optional[str] = None
    typecheck_cmd: Optional[str] = None
    bench_config: Optional[dict[str, Any]] = None


class RepoResponse(BaseModel):
    """Response schema for a single repository."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    org_id: uuid.UUID
    github_repo_id: Optional[int]
    github_full_name: Optional[str] = None
    default_branch: str
    package_manager: Optional[str]
    install_cmd: Optional[str]
    build_cmd: Optional[str]
    test_cmd: Optional[str]
    typecheck_cmd: Optional[str] = None
    bench_config: Optional[dict[str, Any]]
    created_at: datetime


class RepoListResponse(BaseModel):
    """Paginated list of repositories."""

    repos: list[RepoResponse]
    count: int
