"""Auto-pause logic for runaway failure detection.

Repos are automatically paused when:
  - consecutive_setup_failures >= SETUP_FAILURE_THRESHOLD (3)
    Setup failures = install step fails for N consecutive runs.
  - consecutive_flaky_runs >= FLAKY_THRESHOLD (5)
    Flaky runs = tests only pass on the second attempt for M consecutive runs.

Pausing prevents further scheduled runs and sets a flag visible in the UI.
A human must explicitly unpause the repo after reviewing the failure reason.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Settings
from app.scheduling.budget import get_or_create_settings

logger = logging.getLogger(__name__)

# Number of consecutive setup failures before auto-pausing
SETUP_FAILURE_THRESHOLD = 3

# Number of consecutive flaky runs before auto-pausing
FLAKY_THRESHOLD = 5


class RepoPaused(Exception):
    """Raised when a run is attempted on a paused repository."""

    def __init__(self, repo_id: uuid.UUID, reason: str):
        self.repo_id = repo_id
        self.reason = reason
        super().__init__(f"Repo {repo_id} is paused: {reason}")


async def check_not_paused(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> None:
    """Raise RepoPaused if the repository is currently paused.

    Called at run-start to prevent executing paused repos.
    """
    settings = await get_or_create_settings(db, repo_id)
    if settings.paused:
        reason = _pause_reason(settings)
        raise RepoPaused(repo_id, reason)


async def record_setup_failure(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> bool:
    """Record a setup (install) failure and potentially auto-pause.

    Returns True if the repo was paused as a result.
    Resets flaky counter since a setup failure is a different failure mode.
    """
    settings = await _fetch_or_create_persisted(db, repo_id)

    settings.consecutive_setup_failures += 1
    settings.consecutive_flaky_runs = 0  # Different failure mode — reset

    should_pause = settings.consecutive_setup_failures >= SETUP_FAILURE_THRESHOLD

    if should_pause and not settings.paused:
        settings.paused = True
        logger.warning(
            "Auto-pausing repo %s after %d consecutive setup failures",
            repo_id, settings.consecutive_setup_failures,
        )

    await db.flush()
    return should_pause


async def record_flaky_run(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> bool:
    """Record a flaky test run (tests passed only on the second attempt).

    Returns True if the repo was paused as a result.
    """
    settings = await _fetch_or_create_persisted(db, repo_id)

    settings.consecutive_flaky_runs += 1
    # A flaky run is not a setup failure — don't touch that counter

    should_pause = settings.consecutive_flaky_runs >= FLAKY_THRESHOLD

    if should_pause and not settings.paused:
        settings.paused = True
        logger.warning(
            "Auto-pausing repo %s after %d consecutive flaky runs",
            repo_id, settings.consecutive_flaky_runs,
        )

    await db.flush()
    return should_pause


async def record_successful_run(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> None:
    """Reset failure counters after a clean run.

    A run is "clean" when install succeeds and tests pass on the first attempt.
    """
    settings = await _fetch_or_create_persisted(db, repo_id)

    settings.consecutive_setup_failures = 0
    settings.consecutive_flaky_runs = 0
    settings.last_run_at = datetime.now(timezone.utc)

    await db.flush()
    logger.debug("Reset failure counters for repo %s after successful run", repo_id)


async def unpause_repo(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> None:
    """Manually unpause a repository.

    Resets all failure counters so the repo can run again.
    This is a human-initiated action via the settings API.
    """
    settings = await _fetch_or_create_persisted(db, repo_id)

    settings.paused = False
    settings.consecutive_setup_failures = 0
    settings.consecutive_flaky_runs = 0

    await db.flush()
    logger.info("Repo %s manually unpaused and failure counters reset", repo_id)


def _pause_reason(settings: Settings) -> str:
    """Build a human-readable explanation of why a repo is paused."""
    if settings.consecutive_setup_failures >= SETUP_FAILURE_THRESHOLD:
        return (
            f"Setup failed {settings.consecutive_setup_failures} times consecutively. "
            "Check that install_cmd is correct and dependencies are resolvable."
        )
    if settings.consecutive_flaky_runs >= FLAKY_THRESHOLD:
        return (
            f"Tests were flaky for {settings.consecutive_flaky_runs} consecutive runs. "
            "The test suite may be non-deterministic or environment-dependent."
        )
    return "Manually paused by administrator."


async def _fetch_or_create_persisted(
    db: AsyncSession,
    repo_id: uuid.UUID,
) -> Settings:
    """Fetch existing settings or create and persist a new default row."""
    result = await db.execute(
        select(Settings).where(Settings.repo_id == repo_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    new_settings = Settings(
        repo_id=repo_id,
        paused=False,
        consecutive_setup_failures=0,
        consecutive_flaky_runs=0,
    )
    db.add(new_settings)
    await db.flush()
    return new_settings
