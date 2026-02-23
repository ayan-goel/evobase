"""Pydantic schemas for the per-repo settings endpoints.

GET /repos/{repo_id}/settings  -> SettingsResponse
PUT /repos/{repo_id}/settings  -> SettingsUpdateRequest -> SettingsResponse
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    """Full settings payload returned to the client."""

    model_config = {"from_attributes": True}

    repo_id: uuid.UUID
    compute_budget_minutes: int
    max_prs_per_day: int
    max_proposals_per_run: int
    max_candidates_per_run: int
    schedule: str
    paused: bool
    consecutive_setup_failures: int
    consecutive_flaky_runs: int
    last_run_at: Optional[datetime] = None
    # LLM model configuration
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    # Baseline execution strategy controls
    execution_mode: str = "adaptive"
    max_strategy_attempts: int = 2


class SettingsUpdateRequest(BaseModel):
    """Partial update — all fields are optional.

    Only provided fields are applied; omitted fields keep their current values.
    """

    compute_budget_minutes: Optional[int] = Field(
        default=None, gt=0, description="Daily compute budget in minutes"
    )
    max_prs_per_day: Optional[int] = Field(
        default=None, ge=1, le=50, description="Maximum proposals opened per 24-hour window"
    )
    max_proposals_per_run: Optional[int] = Field(
        default=None, gt=0, description="Maximum accepted proposals per run"
    )
    max_candidates_per_run: Optional[int] = Field(
        default=None, gt=0, description="Maximum patch validation attempts per run"
    )
    schedule: Optional[str] = Field(
        default=None,
        description='Cron expression for scheduled runs, e.g. "0 2 * * *"',
    )
    paused: Optional[bool] = Field(
        default=None, description="Whether scheduled runs are paused for this repo"
    )
    llm_provider: Optional[str] = Field(
        default=None, description='LLM provider: "openai", "anthropic", or "google"'
    )
    llm_model: Optional[str] = Field(
        default=None, description="Model name within the chosen provider"
    )
    execution_mode: Optional[str] = Field(
        default=None,
        pattern="^(strict|adaptive)$",
        description='Execution strategy mode: "strict" or "adaptive"',
    )
    max_strategy_attempts: Optional[int] = Field(
        default=None,
        ge=1,
        le=3,
        description="Maximum baseline strategy attempts per run (1-3)",
    )
