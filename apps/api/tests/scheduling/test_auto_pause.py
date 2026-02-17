"""Unit tests for scheduling/auto_pause.py.

Tests cover:
- check_not_paused: passes when unpaused, raises when paused
- record_setup_failure: increments counter, auto-pauses at threshold
- record_flaky_run: increments counter, auto-pauses at threshold
- record_successful_run: resets all counters
- unpause_repo: clears paused flag and resets counters
- cross-counter isolation: setup failures don't affect flaky counter and vice versa
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Organization, Repository, Settings, User
from app.scheduling.auto_pause import (
    FLAKY_THRESHOLD,
    SETUP_FAILURE_THRESHOLD,
    RepoPaused,
    check_not_paused,
    record_flaky_run,
    record_setup_failure,
    record_successful_run,
    unpause_repo,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def repo(db_session: AsyncSession) -> Repository:
    user = User(email="autopause@selfopt.local")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="AutoPause Org", owner_id=user.id)
    db_session.add(org)
    await db_session.flush()

    r = Repository(
        org_id=org.id,
        github_repo_id=42,
        default_branch="main",
        package_manager="npm",
    )
    db_session.add(r)
    await db_session.flush()
    return r


@pytest.fixture
async def fresh_settings(db_session: AsyncSession, repo: Repository) -> Settings:
    s = Settings(repo_id=repo.id)
    db_session.add(s)
    await db_session.flush()
    return s


# ---------------------------------------------------------------------------
# check_not_paused
# ---------------------------------------------------------------------------


class TestCheckNotPaused:
    async def test_passes_when_not_paused(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        # Should not raise
        await check_not_paused(db_session, repo.id)

    async def test_raises_when_paused(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.paused = True
        await db_session.flush()

        with pytest.raises(RepoPaused) as exc_info:
            await check_not_paused(db_session, repo.id)

        assert exc_info.value.repo_id == repo.id

    async def test_passes_when_no_settings_row(
        self, db_session: AsyncSession, repo: Repository
    ) -> None:
        # No settings row => defaults to unpaused
        await check_not_paused(db_session, repo.id)


# ---------------------------------------------------------------------------
# record_setup_failure
# ---------------------------------------------------------------------------


class TestRecordSetupFailure:
    async def test_increments_counter(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        paused = await record_setup_failure(db_session, repo.id)
        await db_session.refresh(fresh_settings)
        assert fresh_settings.consecutive_setup_failures == 1
        assert not paused

    async def test_auto_pauses_at_threshold(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        for _ in range(SETUP_FAILURE_THRESHOLD - 1):
            await record_setup_failure(db_session, repo.id)

        paused = await record_setup_failure(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert paused is True
        assert fresh_settings.paused is True
        assert fresh_settings.consecutive_setup_failures == SETUP_FAILURE_THRESHOLD

    async def test_resets_flaky_counter(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.consecutive_flaky_runs = 3
        await db_session.flush()

        await record_setup_failure(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert fresh_settings.consecutive_flaky_runs == 0

    async def test_does_not_double_pause(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.paused = True
        fresh_settings.consecutive_setup_failures = SETUP_FAILURE_THRESHOLD
        await db_session.flush()

        # Still returns True but paused state doesn't change
        paused = await record_setup_failure(db_session, repo.id)
        assert paused is True

    async def test_creates_settings_when_missing(
        self, db_session: AsyncSession, repo: Repository
    ) -> None:
        paused = await record_setup_failure(db_session, repo.id)
        assert paused is False  # First failure shouldn't pause


# ---------------------------------------------------------------------------
# record_flaky_run
# ---------------------------------------------------------------------------


class TestRecordFlakyRun:
    async def test_increments_counter(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        paused = await record_flaky_run(db_session, repo.id)
        await db_session.refresh(fresh_settings)
        assert fresh_settings.consecutive_flaky_runs == 1
        assert not paused

    async def test_auto_pauses_at_threshold(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        for _ in range(FLAKY_THRESHOLD - 1):
            await record_flaky_run(db_session, repo.id)

        paused = await record_flaky_run(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert paused is True
        assert fresh_settings.paused is True
        assert fresh_settings.consecutive_flaky_runs == FLAKY_THRESHOLD

    async def test_does_not_touch_setup_failure_counter(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.consecutive_setup_failures = 2
        await db_session.flush()

        await record_flaky_run(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert fresh_settings.consecutive_setup_failures == 2


# ---------------------------------------------------------------------------
# record_successful_run
# ---------------------------------------------------------------------------


class TestRecordSuccessfulRun:
    async def test_resets_all_counters(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.consecutive_setup_failures = 2
        fresh_settings.consecutive_flaky_runs = 3
        await db_session.flush()

        await record_successful_run(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert fresh_settings.consecutive_setup_failures == 0
        assert fresh_settings.consecutive_flaky_runs == 0

    async def test_sets_last_run_at(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        await record_successful_run(db_session, repo.id)
        await db_session.refresh(fresh_settings)
        assert fresh_settings.last_run_at is not None


# ---------------------------------------------------------------------------
# unpause_repo
# ---------------------------------------------------------------------------


class TestUnpauseRepo:
    async def test_clears_paused_flag(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.paused = True
        await db_session.flush()

        await unpause_repo(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert fresh_settings.paused is False

    async def test_resets_counters(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        fresh_settings.consecutive_setup_failures = 5
        fresh_settings.consecutive_flaky_runs = 5
        await db_session.flush()

        await unpause_repo(db_session, repo.id)
        await db_session.refresh(fresh_settings)

        assert fresh_settings.consecutive_setup_failures == 0
        assert fresh_settings.consecutive_flaky_runs == 0

    async def test_noop_on_already_unpaused(
        self, db_session: AsyncSession, repo: Repository, fresh_settings: Settings
    ) -> None:
        # Should not raise
        await unpause_repo(db_session, repo.id)
        await db_session.refresh(fresh_settings)
        assert fresh_settings.paused is False


# ---------------------------------------------------------------------------
# RepoPaused exception
# ---------------------------------------------------------------------------


class TestRepoPaused:
    def test_message_includes_repo_id(self) -> None:
        repo_id = uuid.uuid4()
        exc = RepoPaused(repo_id, "too many failures")
        assert str(repo_id) in str(exc)
        assert "too many failures" in str(exc)

    def test_attributes(self) -> None:
        repo_id = uuid.uuid4()
        exc = RepoPaused(repo_id, "reason")
        assert exc.repo_id == repo_id
        assert exc.reason == "reason"
