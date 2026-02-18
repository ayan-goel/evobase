"""Pydantic schemas for auth endpoints."""

import uuid
from typing import Optional

from pydantic import BaseModel


class GitHubCallbackRequest(BaseModel):
    supabase_user_id: Optional[uuid.UUID] = None
    github_id: int
    github_login: str
    avatar_url: str
    email: str


class GitHubCallbackResponse(BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID


class MeResponse(BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID
