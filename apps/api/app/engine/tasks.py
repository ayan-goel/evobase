"""Celery task definitions for optimization run orchestration.

Tasks are the bridge between the API (enqueue) and the runner (execute).
Each task receives a run_id, transitions the run through its state machine,
and delegates actual execution to the runner.

Phase 13: The full pipeline is:
  1. Transition run: queued -> running
  2. Checkout repo + detect stack (Phase 5 runner)
  3. Run baseline pipeline (Phase 6 runner)
  4. Run LLM agent cycle: discover opportunities + generate patches (Phase 13)
  5. Validate each patch (Phase 9 runner)
  6. Package accepted proposals (Phase 10 runner)
  7. Transition run: running -> completed | failed
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.engine.queue import celery_app
from app.runs.service import RunService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="coreloop.execute_run",
    bind=True,
    max_retries=0,
    # An agentic run involves: baseline (up to 2 attempts) + 10 LLM file
    # analysis calls + up to 5×3 patch generation calls + up to 5 validation
    # runs. Each LLM call can take 1–2 minutes. Allow up to 90 minutes.
    # The global task_soft_time_limit in queue.py is only for short Beat tasks.
    soft_time_limit=5400,   # 90 min — graceful shutdown via SoftTimeLimitExceeded
    time_limit=5520,        # 92 min — hard kill if soft handler hangs
)
def execute_run(self, run_id: str, trace_id: str = "") -> dict:
    """Execute a full optimization run with LLM agent pipeline.

    The task is synchronous (Celery workers run sync tasks by default).
    Async agent calls are executed via asyncio.run() within this sync context.
    DB access uses a synchronous session since Celery doesn't run an
    asyncio event loop.

    Args:
        run_id: UUID of the run to execute.
        trace_id: X-Request-ID from the originating HTTP request. Bound to
                  the structlog context so all log lines for this run carry
                  the same ID as the API request that created it.
    """
    logger.info(
        "Starting run execution: run_id=%s trace_id=%s",
        run_id, trace_id or "(none)",
    )

    # Store the Celery task ID so the cancel endpoint can revoke it
    try:
        from app.runs.events import store_task_id
        store_task_id(run_id, self.request.id)
    except Exception:
        logger.debug("Could not store task ID for run %s", run_id, exc_info=True)

    run_service = RunService()

    try:
        # Transition: queued -> running
        logger.info("Run %s: transitioning to running...", run_id)
        run_service.transition_to_running(run_id)
        logger.info("Run %s: transition complete, starting pipeline...", run_id)

        # Execute the full pipeline
        result = run_service.execute_full_pipeline(run_id)

        # Transition: running -> completed
        run_service.transition_to_completed(run_id, result)

        logger.info("Run completed successfully: %s", run_id)
        return {"run_id": run_id, "status": "completed", **result}

    except Exception as exc:
        logger.error(
            "Run failed: %s — %s: %s", run_id, type(exc).__name__, str(exc),
            exc_info=True,
        )

        try:
            from app.runs.events import publish_event
            publish_event(run_id, "run.failed", "run", {"error": str(exc)[:500]})
        except Exception:
            pass

        try:
            run_service.transition_to_failed(run_id, str(exc))
        except Exception as inner:
            logger.error(
                "Run %s: could not transition to failed: %s", run_id, inner
            )

        return {"run_id": run_id, "status": "failed", "error": str(exc)}
