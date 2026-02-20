"""Budget enforcement for optimization run execution.

Checks are applied before a run starts and during execution to prevent
runaway compute costs. All limits come from the per-repo Settings record.

Three hard limits:
  1. compute_budget_minutes — total CPU-minutes used today vs daily cap
  2. max_proposals_per_run  — accepted proposals already in this run
  3. max_candidates_per_run — patch validation attempts already in this run

Exceeding any limit raises BudgetExceeded so the caller can stop gracefully.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Artifact, Proposal, Run, Settings

logger = logging.getLogger(__name__)

# Minutes of compute assumed consumed per run if no explicit timer is tracked.
# Used as a conservative estimate when actual timing data isn't available.
COMPUTE_MINUTES_PER_RUN_ESTIMATE = 5

# Thresholds are read from Settings; these are fallback defaults.
DEFAULT_BUDGET_MINUTES = 60
DEFAULT_MAX_PROPOSALS = 10
DEFAULT_MAX_CANDIDATES = 20


class BudgetExceeded(Exception):
    """Raised when a budget limit is exceeded.

    Carries which limit was hit and the current vs allowed values.
    """

    def __init__(self, limit: str, current: int, allowed: int):
        self.limit = limit
        self.current = current
        self.allowed = allowed
        super().__init__(
            f"Budget exceeded: {limit} = {current} / {allowed}"
        )


async def get_or_create_settings(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> Settings:
    """Fetch existing settings or return a default Settings instance.

    Does NOT persist the defaults — callers that need to save should
    add and commit the returned object explicitly.
    """
    result = await db.execute(
        select(Settings).where(Settings.repo_id == repo_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # Return an in-memory default (not persisted)
    return Settings(
        repo_id=repo_id,
        compute_budget_minutes=DEFAULT_BUDGET_MINUTES,
        max_prs_per_day=5,
        max_proposals_per_run=DEFAULT_MAX_PROPOSALS,
        max_candidates_per_run=DEFAULT_MAX_CANDIDATES,
        schedule="0 2 * * *",
        paused=False,
        consecutive_setup_failures=0,
        consecutive_flaky_runs=0,
    )


async def check_compute_budget(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> None:
    """Check whether the repo has remaining compute budget for today.

    Counts runs completed today and estimates compute used.
    Raises BudgetExceeded if the daily cap would be exceeded.
    """
    settings = await get_or_create_settings(db, repo_id)
    budget = settings.compute_budget_minutes

    # Count runs for this repo today
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    result = await db.execute(
        select(func.count(Run.id)).where(
            Run.repo_id == repo_id,
            Run.created_at >= today_start,
            Run.status.in_(["completed", "failed", "running"]),
        )
    )
    runs_today = result.scalar_one() or 0
    estimated_used = runs_today * COMPUTE_MINUTES_PER_RUN_ESTIMATE

    if estimated_used >= budget:
        logger.warning(
            "Compute budget exceeded for repo %s: %d min used / %d min budget",
            repo_id, estimated_used, budget,
        )
        raise BudgetExceeded("compute_minutes", estimated_used, budget)

    logger.debug(
        "Compute budget OK for repo %s: %d min used / %d min budget",
        repo_id, estimated_used, budget,
    )


async def check_max_proposals(
    db: AsyncSession,
    run_id: uuid.UUID,
) -> None:
    """Check whether this run has reached its proposal cap.

    Raises BudgetExceeded if the max_proposals_per_run limit is hit.
    """
    # Get repo_id for the run to look up settings
    run_result = await db.execute(select(Run).where(Run.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        return

    settings = await get_or_create_settings(db, run.repo_id)
    max_proposals = settings.max_proposals_per_run

    proposal_count_result = await db.execute(
        select(func.count(Proposal.id)).where(Proposal.run_id == run_id)
    )
    current = proposal_count_result.scalar_one() or 0

    if current >= max_proposals:
        logger.info(
            "Max proposals reached for run %s: %d / %d",
            run_id, current, max_proposals,
        )
        raise BudgetExceeded("max_proposals_per_run", current, max_proposals)


async def check_max_candidates(
    db: AsyncSession,
    run_id: uuid.UUID,
    candidate_count: int,
) -> None:
    """Check whether this run has reached its candidate validation cap.

    candidate_count is the number of patch validation attempts so far.
    Raises BudgetExceeded if the max_candidates_per_run limit is hit.
    """
    run_result = await db.execute(select(Run).where(Run.id == run_id))
    run = run_result.scalar_one_or_none()
    if not run:
        return

    settings = await get_or_create_settings(db, run.repo_id)
    max_candidates = settings.max_candidates_per_run

    if candidate_count >= max_candidates:
        logger.info(
            "Max candidates reached for run %s: %d / %d",
            run_id, candidate_count, max_candidates,
        )
        raise BudgetExceeded("max_candidates_per_run", candidate_count, max_candidates)
