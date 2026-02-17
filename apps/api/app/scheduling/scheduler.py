"""Celery beat scheduler for nightly optimization runs.

The `trigger_scheduled_runs` task is executed periodically by Celery beat.
It queries all non-paused repos whose schedule indicates a run is due,
respects the daily compute budget, and enqueues `execute_run` tasks.

Schedule expression examples (standard cron):
  "0 2 * * *"   — every day at 02:00 UTC
  "0 */6 * * *" — every 6 hours
  "0 2 * * 1"   — every Monday at 02:00 UTC

Celery beat is started with:
  celery -A app.engine.queue beat --loglevel=info
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.engine.queue import celery_app

logger = logging.getLogger(__name__)

# How often beat checks for due repos (in seconds). This is independent of
# each repo's cron schedule; it's the polling interval for the trigger task.
TRIGGER_INTERVAL_SECONDS = 1800  # 30 minutes


def _is_schedule_due(schedule: str, last_run_at: Optional[datetime]) -> bool:
    """Check whether a cron schedule is due given the last run time.

    Uses a conservative heuristic: if the schedule is daily (e.g. "0 2 * * *")
    and the last run was more than 23 hours ago (or never), it's due.

    For MVP, we parse only the hour field of the daily cron. Full cron parsing
    (e.g. via `croniter`) would be added in a production hardening pass.

    Args:
        schedule: A cron string such as "0 2 * * *".
        last_run_at: UTC timestamp of the most recent run, or None if never run.

    Returns:
        True if a run should be triggered.
    """
    now = datetime.now(timezone.utc)

    # Never run — always due
    if last_run_at is None:
        return True

    # Parse hour from cron string "minute hour ..."
    # Only handles simple "0 H * * *" patterns for MVP.
    try:
        parts = schedule.strip().split()
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            target_hour = int(parts[1])
            # Due if last run was before today's scheduled hour
            today_target = now.replace(
                hour=target_hour, minute=0, second=0, microsecond=0
            )
            return last_run_at < today_target and now >= today_target
    except (ValueError, IndexError):
        logger.warning("Could not parse cron schedule: %r", schedule)

    # Fallback: always trigger if last run > 23 hours ago
    age_hours = (now - last_run_at).total_seconds() / 3600
    return age_hours >= 23.0


@celery_app.task(
    name="selfopt.trigger_scheduled_runs",
    bind=True,
    max_retries=0,
    ignore_result=True,
)
def trigger_scheduled_runs(self) -> None:
    """Periodic task: find repos due for a run and enqueue them.

    Queries all non-paused repos via a synchronous DB session and dispatches
    `execute_run` for each eligible repo.

    This task runs every TRIGGER_INTERVAL_SECONDS as configured in beat_schedule.
    """
    logger.info("Scheduler tick: checking for repos due for a run")

    try:
        _dispatch_due_repos()
    except Exception:
        logger.exception("Scheduler tick failed")


def _dispatch_due_repos() -> None:
    """Core scheduling logic — separated for testability."""
    # Import here to avoid circular imports at module load time.
    # These imports are synchronous — the scheduler task uses a sync session.
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.db.models import Repository, Run, Settings
    from app.engine.tasks import execute_run

    app_settings = get_settings()
    engine = create_engine(
        app_settings.database_url.replace("postgresql+asyncpg", "postgresql"),
        echo=False,
    )

    with Session(engine) as db:
        # Fetch all non-paused repos that have settings configured
        rows = db.execute(
            select(Repository, Settings)
            .join(Settings, Settings.repo_id == Repository.id)
            .where(Settings.paused.is_(False))
        ).all()

        dispatched = 0
        for repo, settings in rows:
            if not _is_schedule_due(settings.schedule, settings.last_run_at):
                continue

            # Compute budget check: count runs today
            from datetime import datetime, timezone
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            runs_today = db.execute(
                select(Run)
                .where(Run.repo_id == repo.id)
                .where(Run.created_at >= today_start)
            ).scalars().all()

            estimated_minutes = len(runs_today) * 5  # 5 min per run estimate
            if estimated_minutes >= settings.compute_budget_minutes:
                logger.info(
                    "Skipping repo %s: compute budget exhausted (%d min used / %d allowed)",
                    repo.id, estimated_minutes, settings.compute_budget_minutes,
                )
                continue

            # Create a queued run record
            new_run = Run(
                repo_id=repo.id,
                sha="HEAD",
                status="queued",
            )
            db.add(new_run)
            db.flush()

            # Enqueue the Celery task
            execute_run.delay(str(new_run.id))
            dispatched += 1
            logger.info("Scheduled run %s for repo %s", new_run.id, repo.id)

        db.commit()
        logger.info("Scheduler tick complete: %d runs dispatched", dispatched)


# ---------------------------------------------------------------------------
# Celery beat schedule — applied when the Celery queue module is imported.
# Beat is started separately: celery -A app.engine.queue beat
# ---------------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    "trigger-scheduled-runs": {
        "task": "selfopt.trigger_scheduled_runs",
        "schedule": TRIGGER_INTERVAL_SECONDS,
    },
}
