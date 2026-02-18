"""Pydantic schemas for GitHub integration endpoints."""

import uuid
from typing import Optional

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    """Acknowledgement response for webhook events."""

    received: bool
    event: str
    action: str


class CreatePrResponse(BaseModel):
    """Response after successfully creating a PR from a proposal."""

    proposal_id: uuid.UUID
    pr_url: str


class InstallationResponse(BaseModel):
    id: str
    installation_id: int
    account_login: str
    account_id: int


class InstallationListResponse(BaseModel):
    installations: list[InstallationResponse]
    count: int


class GitHubRepoItem(BaseModel):
    github_repo_id: int
    full_name: str
    name: str
    default_branch: str = "main"
    private: bool = False


class InstallationReposResponse(BaseModel):
    repos: list[GitHubRepoItem]
    count: int


class LinkInstallationRequest(BaseModel):
    installation_id: int
    account_login: Optional[str] = None
    account_id: Optional[int] = None


class LinkInstallationResponse(BaseModel):
    installation_id: int
    linked: bool
