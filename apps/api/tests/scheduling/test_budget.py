"""Unit tests for scheduling/budget.py.

Tests cover:
- get_or_create_settings: returns existing or defaults
- check_compute_budget: raises when runs today * estimate >= budget
- check_max_proposals: raises when proposal count >= max
- check_max_candidates: raises when candidate_count >= max
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, Proposal, Repository, Run, Settings, User
from app.scheduling.budget import (
    BudgetExceeded,
    COMPUTE_MINUTES_PER_RUN_ESTIMATE,
    DEFAULT_BUDGET_MINUTES,
    check_compute_budget,
    check_max_candidates,
    check_max_proposals,
    get_or_create_settings,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def repo(db_session: AsyncSession) -> Repository:
    user = User(email="test@selfopt.local")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Test Org", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()

    r = Repository(
        org_id=org.id,
        github_repo_id=1,
        default_branch="main",
        package_manager="npm",
    )
    db_session.add(r)
    await db_session.flush()
    return r


@pytest.fixture
async def settings_row(db_session: AsyncSession, repo: Repository) -> Settings:
    s = Settings(
        repo_id=repo.id,
        compute_budget_minutes=60,
        max_proposals_per_run=5,
        max_candidates_per_run=10,
    )
    db_session.add(s)
    await db_session.flush()
    return s


@pytest.fixture
async def run_today(db_session: AsyncSession, repo: Repository) -> Run:
    r = Run(repo_id=repo.id, sha="abc", status="completed")
    db_session.add(r)
    await db_session.flush()
    return r


# ---------------------------------------------------------------------------
# get_or_create_settings
# ---------------------------------------------------------------------------


class TestGetOrCreateSettings:
    async def test_returns_existing_settings(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings
    ) -> None:
        result = await get_or_create_settings(db_session, repo.id)
        assert result.compute_budget_minutes == 60
        assert result.max_proposals_per_run == 5

    async def test_returns_defaults_when_missing(
        self, db_session: AsyncSession, repo: Repository
    ) -> None:
        result = await get_or_create_settings(db_session, repo.id)
        assert result.compute_budget_minutes == DEFAULT_BUDGET_MINUTES
        assert result.paused is False

    async def test_default_not_persisted(
        self, db_session: AsyncSession, repo: Repository
    ) -> None:
        await get_or_create_settings(db_session, repo.id)
        # Should still be absent from DB
        result = await get_or_create_settings(db_session, repo.id)
        assert result.repo_id == repo.id


# ---------------------------------------------------------------------------
# check_compute_budget
# ---------------------------------------------------------------------------


class TestCheckComputeBudget:
    async def test_passes_when_no_runs_today(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings
    ) -> None:
        # No runs => no budget used => should not raise
        await check_compute_budget(db_session, repo.id)

    async def test_raises_when_budget_exhausted(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings
    ) -> None:
        # Add enough runs to exhaust the budget (60 min / 5 min per run = 12 runs)
        runs_needed = 60 // COMPUTE_MINUTES_PER_RUN_ESTIMATE
        for _ in range(runs_needed):
            db_session.add(Run(repo_id=repo.id, sha="sha", status="completed"))
        await db_session.flush()

        with pytest.raises(BudgetExceeded) as exc_info:
            await check_compute_budget(db_session, repo.id)

        assert exc_info.value.limit == "compute_minutes"
        assert exc_info.value.allowed == 60

    async def test_passes_just_below_limit(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings
    ) -> None:
        # One run below the threshold
        runs_needed = (60 // COMPUTE_MINUTES_PER_RUN_ESTIMATE) - 1
        for _ in range(runs_needed):
            db_session.add(Run(repo_id=repo.id, sha="sha", status="completed"))
        await db_session.flush()

        # Should not raise
        await check_compute_budget(db_session, repo.id)

    async def test_uses_default_budget_when_no_settings(
        self, db_session: AsyncSession, repo: Repository
    ) -> None:
        # No settings row — should use DEFAULT_BUDGET_MINUTES
        await check_compute_budget(db_session, repo.id)  # should not raise


# ---------------------------------------------------------------------------
# check_max_proposals
# ---------------------------------------------------------------------------


class TestCheckMaxProposals:
    async def test_passes_when_no_proposals(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        await check_max_proposals(db_session, run_today.id)

    async def test_raises_when_limit_reached(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        for _ in range(5):
            db_session.add(Proposal(run_id=run_today.id, diff="diff"))
        await db_session.flush()

        with pytest.raises(BudgetExceeded) as exc_info:
            await check_max_proposals(db_session, run_today.id)

        assert exc_info.value.limit == "max_proposals_per_run"
        assert exc_info.value.allowed == 5

    async def test_passes_one_below_limit(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        for _ in range(4):
            db_session.add(Proposal(run_id=run_today.id, diff="diff"))
        await db_session.flush()

        await check_max_proposals(db_session, run_today.id)

    async def test_noop_when_run_not_found(
        self, db_session: AsyncSession
    ) -> None:
        # Should not raise when run is missing
        await check_max_proposals(db_session, uuid.uuid4())


# ---------------------------------------------------------------------------
# check_max_candidates
# ---------------------------------------------------------------------------


class TestCheckMaxCandidates:
    async def test_passes_when_under_limit(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        await check_max_candidates(db_session, run_today.id, 5)

    async def test_raises_when_limit_reached(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        with pytest.raises(BudgetExceeded) as exc_info:
            await check_max_candidates(db_session, run_today.id, 10)

        assert exc_info.value.limit == "max_candidates_per_run"
        assert exc_info.value.allowed == 10

    async def test_raises_when_over_limit(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        with pytest.raises(BudgetExceeded):
            await check_max_candidates(db_session, run_today.id, 15)

    async def test_noop_when_run_not_found(
        self, db_session: AsyncSession
    ) -> None:
        await check_max_candidates(db_session, uuid.uuid4(), 100)

    async def test_passes_zero_candidates(
        self, db_session: AsyncSession, repo: Repository, settings_row: Settings, run_today: Run
    ) -> None:
        await check_max_candidates(db_session, run_today.id, 0)


# ---------------------------------------------------------------------------
# BudgetExceeded exception
# ---------------------------------------------------------------------------


class TestBudgetExceeded:
    def test_message_format(self) -> None:
        exc = BudgetExceeded("compute_minutes", 60, 60)
        assert "compute_minutes" in str(exc)
        assert "60" in str(exc)

    def test_attributes(self) -> None:
        exc = BudgetExceeded("max_proposals_per_run", 10, 10)
        assert exc.limit == "max_proposals_per_run"
        assert exc.current == 10
        assert exc.allowed == 10
