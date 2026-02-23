"""Run service layer with state machine enforcement.

Manages run lifecycle transitions and delegates execution to the runner package.

State machine:
    queued -> running -> completed
                     \\-> failed

The full optimization pipeline runs entirely inside execute_full_pipeline():
  1. Load repository + settings from the DB
  2. Clone the repo (sandbox/checkout.py — includes SSRF guard)
  3. Detect the tech stack (detector/orchestrator.py)
  4. Run the baseline pipeline (validator/executor.py)
  5. Run the LLM agent cycle (agent/orchestrator.py) — discover + patch + validate
  6. Write proposals, opportunities, and attempts back to the DB
  7. Upload artifacts (baseline.json, diff.patch, trace.json) via the API
  8. Update settings (last_run_at, consecutive counters)
"""

import asyncio
import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Attempt, Opportunity, Proposal, Repository, Run, Settings
from app.db.sync_session import get_sync_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running"},
    "running": {"completed", "failed"},
}


def validate_transition(current: str, target: str) -> None:
    """Enforce the run state machine.

    Raises ValueError if the transition is not allowed.
    """
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(
            f"Invalid run state transition: {current} -> {target}. "
            f"Allowed transitions from '{current}': {allowed or 'none (terminal state)'}"
        )


# ---------------------------------------------------------------------------
# RunService — synchronous, for Celery tasks
# ---------------------------------------------------------------------------


class RunService:
    """Synchronous run service for use within Celery tasks.

    All DB access is synchronous (psycopg2) because Celery workers
    don't have a running asyncio event loop. For async contexts (FastAPI
    routes), use the async helper functions below the class.
    """

    def transition_to_running(self, run_id: str) -> None:
        """Transition a run from queued to running and persist to DB.

        Idempotent: if the run is already ``running`` (e.g. the task was
        redelivered after a worker crash), this is a no-op so the pipeline
        can proceed rather than raising a state-machine error.
        """
        logger.info("Run %s: opening sync DB session...", run_id)
        with get_sync_db() as session:
            logger.info("Run %s: querying run row...", run_id)
            run = session.get(Run, uuid.UUID(run_id))
            if not run:
                raise ValueError(f"Run {run_id} not found")
            if run.status == "running":
                logger.info("Run %s: already running (redelivered task); continuing", run_id)
                return
            validate_transition(run.status, "running")
            run.status = "running"
            session.commit()
            logger.info("Run %s: committed status change", run_id)
        logger.info("Run %s: queued -> running", run_id)

    def execute_baseline(self, run_id: str) -> dict:
        """Execute baseline pipeline for a run (stub for isolated testing).

        In production, execute_full_pipeline() is called instead.
        This stub is retained for unit tests of the state machine.
        """
        logger.info("Executing baseline for run %s (stub)", run_id)
        return {
            "baseline_completed": True,
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _emit(run_id: str, event_type: str, phase: str, data: Optional[dict] = None) -> None:
        """Best-effort event emission — never raises."""
        try:
            from app.runs.events import publish_event
            publish_event(run_id, event_type, phase, data)
        except Exception:
            pass

    @staticmethod
    def _check_cancelled(run_id: str) -> bool:
        try:
            from app.runs.events import is_cancelled
            return is_cancelled(run_id)
        except Exception:
            return False

    def execute_full_pipeline(self, run_id: str) -> dict:
        """Execute the full LLM agent optimization pipeline.

        Pipeline:
          1. Load repo + settings from DB
          2. Clone the repository (SSRF-guarded)
          3. Detect the tech stack
          4. Run baseline (install + build + test + bench)
          5. Run LLM agent cycle (discover + patch + validate)
          6. Write proposals/opportunities/attempts to DB
          7. Upload artifacts
          8. Update settings counters

        This method bridges from the synchronous Celery context into
        the async agent layer via asyncio.run().
        """
        repo_dir: Optional[Path] = None
        emit = lambda etype, phase, data=None: self._emit(run_id, etype, phase, data)

        try:
            # ----------------------------------------------------------------
            # Step 1: Load repo + settings from DB
            # ----------------------------------------------------------------
            with get_sync_db() as session:
                run = session.get(Run, uuid.UUID(run_id))
                if not run:
                    raise ValueError(f"Run {run_id} not found")
                repo = session.get(Repository, run.repo_id)
                if not repo:
                    raise ValueError(f"Repository for run {run_id} not found")
                settings = session.get(Settings, repo.id)

                repo_id = str(repo.id)
                github_repo_id = repo.github_repo_id
                github_full_name = repo.github_full_name
                installation_id = repo.installation_id
                sha = run.sha
                install_cmd = repo.install_cmd
                build_cmd = repo.build_cmd
                test_cmd = repo.test_cmd
                typecheck_cmd = repo.typecheck_cmd
                root_dir = repo.root_dir
                repo_framework = repo.framework

                # LLM settings — prefer per-repo, fall back to env vars
                llm_provider = settings.llm_provider if settings else "anthropic"
                llm_model = settings.llm_model if settings else "claude-sonnet-4-5"
                max_candidates = (
                    settings.max_candidates_per_run if settings else 20
                )
                max_proposals = (
                    settings.max_proposals_per_run if settings else 10
                )
                execution_mode = settings.execution_mode if settings else "adaptive"
                max_strategy_attempts = (
                    settings.max_strategy_attempts if settings else 2
                )

            # ----------------------------------------------------------------
            # Step 2: Resolve repo URL
            # ----------------------------------------------------------------
            if not github_repo_id and not github_full_name:
                logger.warning(
                    "Run %s: repository has no github_repo_id or github_full_name; cannot clone",
                    run_id,
                )
                return _no_repo_result(run_id)

            # Fetch an installation token for private repos
            clone_token = None
            if installation_id:
                try:
                    from app.github.client import get_installation_token
                    clone_token = asyncio.run(get_installation_token(installation_id))
                except Exception as exc:
                    logger.warning(
                        "Run %s: could not fetch installation token for clone: %s",
                        run_id, exc,
                    )

            from runner.sandbox.checkout import (
                checkout_sha,
                clone_repo,
                get_head_sha,
                redact_repo_url,
            )

            repo_url = _build_repo_url(github_full_name, github_repo_id, token=clone_token)
            logger.info("Run %s: cloning %s", run_id, redact_repo_url(repo_url))
            emit("clone.started", "clone", {"repo": github_full_name})

            # ----------------------------------------------------------------
            # Step 3: Clone
            # ----------------------------------------------------------------
            repo_dir = Path(tempfile.mkdtemp(prefix="coreloop-run-"))

            clone_repo(repo_url=repo_url, workspace_dir=repo_dir)
            if sha:
                try:
                    checkout_sha(repo_dir, sha)
                except RuntimeError as exc:
                    logger.warning(
                        "Run %s: could not checkout SHA %s (%s) — using HEAD",
                        run_id, sha, exc,
                    )

            # Capture the actual HEAD SHA + commit message and persist them
            try:
                head_sha = get_head_sha(repo_dir)

                # Extract commit subject line from the local clone — no extra API call needed
                import subprocess as _subprocess
                _git_msg = _subprocess.run(
                    ["git", "log", "-1", "--format=%s", head_sha],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                commit_message = _git_msg.stdout.strip()[:200] if _git_msg.returncode == 0 else None

                with get_sync_db() as session:
                    run_row = session.get(Run, uuid.UUID(run_id))
                    if run_row:
                        run_row.sha = head_sha
                        run_row.commit_message = commit_message
                        session.commit()
                logger.info("Run %s: HEAD sha=%s msg=%r", run_id, head_sha[:7], commit_message)
                emit("clone.completed", "clone", {
                    "sha": head_sha[:7],
                    "commit_message": commit_message,
                })
            except Exception as exc:
                logger.warning("Run %s: could not capture HEAD SHA: %s", run_id, exc)
                emit("clone.completed", "clone")

            if self._check_cancelled(run_id):
                emit("run.cancelled", "run", {"reason": "User cancelled"})
                return _cancelled_result(run_id)

            # ----------------------------------------------------------------
            # Step 3b: Resolve working directory (monorepo support)
            # ----------------------------------------------------------------
            if root_dir:
                work_dir = repo_dir / root_dir.strip("/")
                if not work_dir.is_dir():
                    logger.error(
                        "Run %s: root_dir '%s' not found in cloned repo",
                        run_id, root_dir,
                    )
                    _increment_failure_counter(run_id, repo_id, "setup")
                    return {
                        "baseline_completed": False,
                        "agent_skipped": True,
                        "reason": "root_dir_not_found",
                        "run_id": run_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                logger.info("Run %s: using subdirectory '%s' as work_dir", run_id, root_dir)
            else:
                work_dir = repo_dir

            # ----------------------------------------------------------------
            # Step 4: Detect stack
            # ----------------------------------------------------------------
            from runner.detector.orchestrator import detect

            detection = detect(work_dir)

            if install_cmd and not detection.install_cmd:
                detection.install_cmd = install_cmd
            if build_cmd and not detection.build_cmd:
                detection.build_cmd = build_cmd
            if test_cmd and not detection.test_cmd:
                detection.test_cmd = test_cmd
            if typecheck_cmd and not detection.typecheck_cmd:
                detection.typecheck_cmd = typecheck_cmd

            logger.info(
                "Run %s: detected pm=%s framework=%s install=%s test=%s",
                run_id,
                detection.package_manager,
                detection.framework,
                detection.install_cmd,
                detection.test_cmd,
            )
            emit("detection.completed", "detection", {
                "language": detection.language,
                "framework": detection.framework,
                "package_manager": detection.package_manager,
                "confidence": detection.confidence,
                "install_cmd": detection.install_cmd,
                "build_cmd": detection.build_cmd,
                "test_cmd": detection.test_cmd,
                "typecheck_cmd": detection.typecheck_cmd,
            })

            if self._check_cancelled(run_id):
                emit("run.cancelled", "run", {"reason": "User cancelled"})
                return _cancelled_result(run_id)

            # ----------------------------------------------------------------
            # Step 5: Persist detected commands back to the Repository row
            # ----------------------------------------------------------------
            with get_sync_db() as session:
                repo_row = session.get(Repository, uuid.UUID(repo_id))
                if repo_row:
                    repo_row.package_manager = repo_row.package_manager or detection.package_manager
                    repo_row.framework = repo_row.framework or detection.framework
                    repo_row.install_cmd = repo_row.install_cmd or detection.install_cmd
                    repo_row.build_cmd = repo_row.build_cmd or detection.build_cmd
                    repo_row.test_cmd = repo_row.test_cmd or detection.test_cmd
                    repo_row.typecheck_cmd = repo_row.typecheck_cmd or detection.typecheck_cmd
                    session.commit()

            # ----------------------------------------------------------------
            # Step 6: Baseline (install + build + test)
            # ----------------------------------------------------------------
            from runner.validator.executor import run_baseline

            emit("baseline.attempt.started", "baseline", {
                "attempt": 1,
                "mode": execution_mode,
                "install_cmd": detection.install_cmd,
                "test_cmd": detection.test_cmd,
            })

            baseline = run_baseline(
                repo_dir=work_dir,
                config=detection,
                execution_mode=execution_mode,
                max_strategy_attempts=max_strategy_attempts,
            )

            for step in baseline.steps:
                emit("baseline.step.completed", "baseline", {
                    "step": step.name,
                    "exit_code": step.exit_code,
                    "duration": round(step.duration_seconds, 1),
                    "success": step.is_success,
                    "stderr_tail": (step.stderr or "")[-500:] if not step.is_success else None,
                    "command": step.command,
                })

            logger.info(
                "Run %s: baseline success=%s steps=%d attempts=%d mode=%s reason=%s",
                run_id,
                baseline.is_success,
                len(baseline.steps),
                baseline.strategy_attempts,
                baseline.strategy_mode,
                baseline.failure_reason_code,
            )

            emit("baseline.completed", "baseline", {
                "success": baseline.is_success,
                "attempts": baseline.strategy_attempts,
                "mode": baseline.strategy_mode,
                "failure_reason": baseline.failure_reason_code,
                "step_count": len(baseline.steps),
            })

            if not baseline.is_success:
                logger.warning(
                    "Run %s: baseline failed — incrementing setup failure counter",
                    run_id,
                )
                # Persist the critical failing step for UI messaging.
                # Baseline failure is only triggered by critical gates
                # (install/test), so prefer those over optional failures
                # like build/typecheck.
                critical_steps = {"install", "test"}
                failed_step = next(
                    (
                        s.name
                        for s in baseline.steps
                        if s.exit_code != 0 and s.name in critical_steps
                    ),
                    next((s.name for s in baseline.steps if s.exit_code != 0), "unknown"),
                )
                try:
                    with get_sync_db() as session:
                        run_row = session.get(Run, uuid.UUID(run_id))
                        if run_row:
                            run_row.failure_step = failed_step
                            session.commit()
                except Exception as exc:
                    logger.warning("Run %s: could not persist failure_step: %s", run_id, exc)

                _increment_failure_counter(run_id, repo_id, "setup")
                emit("run.failed", "run", {
                    "reason": "baseline_failed",
                    "failure_step": failed_step,
                    "failure_reason_code": baseline.failure_reason_code,
                })
                return {
                    "baseline_completed": False,
                    "agent_skipped": True,
                    "reason": "baseline_failed",
                    "failure_step": failed_step,
                    "failure_reason_code": baseline.failure_reason_code,
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            if self._check_cancelled(run_id):
                emit("run.cancelled", "run", {"reason": "User cancelled"})
                return _cancelled_result(run_id)

            # ----------------------------------------------------------------
            # Step 7: Upload baseline artifacts
            # ----------------------------------------------------------------
            _upload_baseline_artifacts(run_id, repo_id, baseline)

            # ----------------------------------------------------------------
            # Step 8: Guard — skip agent cycle if no test command
            # ----------------------------------------------------------------
            if not detection.test_cmd:
                logger.warning(
                    "Run %s: no test command detected — skipping agent cycle "
                    "(proposals without test validation would be untrustworthy)",
                    run_id,
                )
                return {
                    "baseline_completed": True,
                    "agent_skipped": True,
                    "reason": "no_test_cmd",
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # ----------------------------------------------------------------
            # Step 9: LLM agent cycle
            # ----------------------------------------------------------------
            api_key = _resolve_api_key(llm_provider)
            if not api_key:
                logger.warning(
                    "Run %s: no API key for provider=%s — skipping agent cycle",
                    run_id, llm_provider,
                )
                return {
                    "baseline_completed": True,
                    "agent_skipped": True,
                    "reason": "no_llm_api_key",
                    "run_id": run_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            from runner.agent.orchestrator import run_agent_cycle
            from runner.llm.types import LLMConfig

            llm_config = LLMConfig(
                provider=llm_provider,
                model=llm_model,
                api_key=api_key,
                max_tokens=4096,
                temperature=0.2,
                enable_thinking=True,
            )

            seen_signatures = _build_seen_signatures(uuid.UUID(repo_id))

            emit("discovery.started", "discovery", {
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "max_candidates": max_candidates,
            })

            if self._check_cancelled(run_id):
                emit("run.cancelled", "run", {"reason": "User cancelled"})
                return _cancelled_result(run_id)

            cycle_result = asyncio.run(
                run_agent_cycle(
                    repo_dir=work_dir,
                    detection=detection,
                    llm_config=llm_config,
                    baseline=baseline,
                    max_candidates=max_candidates,
                    seen_signatures=seen_signatures,
                )
            )

            logger.info(
                "Run %s: agent cycle done — %d attempted, %d accepted",
                run_id, cycle_result.total_attempted, cycle_result.accepted_count,
            )

            # Emit per-opportunity events for the live timeline
            for i, opp in enumerate(cycle_result.opportunity_for_candidate):
                emit("discovery.opportunity.found", "discovery", {
                    "index": i,
                    "type": opp.type,
                    "location": opp.location,
                    "rationale": opp.rationale,
                    "risk_level": getattr(opp, "risk_level", None),
                    "approaches": getattr(opp, "approaches", []),
                })

            emit("discovery.completed", "discovery", {
                "count": len(cycle_result.opportunity_for_candidate),
            })

            for i, candidate in enumerate(cycle_result.candidate_results):
                opp = cycle_result.opportunity_for_candidate[i] if i < len(cycle_result.opportunity_for_candidate) else None
                variants = (
                    cycle_result.patch_variants_for_candidate[i]
                    if i < len(getattr(cycle_result, "patch_variants_for_candidate", []))
                    else []
                )

                emit("validation.verdict", "validation", {
                    "index": i,
                    "opportunity": opp.location if opp else "unknown",
                    "accepted": candidate.is_accepted,
                    "confidence": candidate.final_verdict.confidence if candidate.final_verdict else None,
                    "reason": candidate.final_verdict.reason if candidate.final_verdict else None,
                    "gates_passed": candidate.final_verdict.gates_passed if candidate.final_verdict else [],
                    "gates_failed": candidate.final_verdict.gates_failed if candidate.final_verdict else [],
                    "approaches_tried": len(variants),
                })

                selection_reason = (
                    cycle_result.selection_reasons[i]
                    if i < len(getattr(cycle_result, "selection_reasons", []))
                    else None
                )
                if candidate.is_accepted and selection_reason:
                    emit("selection.completed", "selection", {
                        "index": i,
                        "reason": selection_reason,
                    })

            # ----------------------------------------------------------------
            # Step 9: Write proposals + opportunities + attempts to DB
            # ----------------------------------------------------------------
            proposals_written = _write_proposals_to_db(
                run_id=run_id,
                repo_id=repo_id,
                cycle_result=cycle_result,
                baseline=baseline,
                max_proposals=max_proposals,
                framework=repo_framework,
            )

            # ----------------------------------------------------------------
            # Step 10: Update settings counters
            # ----------------------------------------------------------------
            _update_settings_after_success(repo_id)

            emit("run.completed", "run", {
                "proposals_created": proposals_written,
                "candidates_attempted": cycle_result.total_attempted,
                "accepted": cycle_result.accepted_count,
            })

            return {
                "baseline_completed": True,
                "agent_completed": True,
                "llm_provider": llm_provider,
                "llm_model": llm_model,
                "proposals_created": proposals_written,
                "candidates_attempted": cycle_result.total_attempted,
                "run_id": run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        finally:
            # Always clean up the checkout directory
            if repo_dir and repo_dir.exists():
                try:
                    shutil.rmtree(repo_dir)
                except Exception as exc:
                    logger.warning("Failed to clean up repo_dir %s: %s", repo_dir, exc)

    def transition_to_completed(self, run_id: str, result: dict) -> None:
        """Transition a run from running to completed and record compute time."""
        with get_sync_db() as session:
            run = session.get(Run, uuid.UUID(run_id))
            if not run:
                logger.warning("transition_to_completed: run %s not found", run_id)
                return
            try:
                validate_transition(run.status, "completed")
            except ValueError:
                logger.warning(
                    "transition_to_completed: skipping invalid transition %s -> completed",
                    run.status,
                )
                return
            run.status = "completed"
            session.commit()
        logger.info("Run %s: running -> completed", run_id)

    def transition_to_failed(self, run_id: str, error: str) -> None:
        """Transition a run from running to failed."""
        with get_sync_db() as session:
            run = session.get(Run, uuid.UUID(run_id))
            if not run:
                logger.error("transition_to_failed: run %s not found", run_id)
                return
            try:
                validate_transition(run.status, "failed")
            except ValueError:
                logger.warning(
                    "transition_to_failed: skipping invalid transition %s -> failed",
                    run.status,
                )
                return
            run.status = "failed"
            session.commit()
        logger.error("Run %s: running -> failed — %s", run_id, error)


# ---------------------------------------------------------------------------
# Proposal + DB writing
# ---------------------------------------------------------------------------


def _write_proposals_to_db(
    run_id: str,
    repo_id: str,
    cycle_result,
    baseline,
    max_proposals: int,
    framework: Optional[str] = None,
) -> int:
    """Write accepted proposals (with opportunities + attempts) to the DB.

    Only accepted candidates become Proposals. All candidates (accepted and
    rejected) are written as Opportunity + Attempt rows for full trace visibility.

    Returns the number of Proposal rows created.
    """
    proposals_created = 0

    with get_sync_db() as session:
        for i, (candidate, agent_opp) in enumerate(
            zip(
                cycle_result.candidate_results,
                cycle_result.opportunity_for_candidate,
            )
        ):
            # Write Opportunity row
            opp_row = Opportunity(
                run_id=uuid.UUID(run_id),
                type=agent_opp.type,
                location=agent_opp.location,
                rationale=agent_opp.rationale,
                risk_score=float(agent_opp.risk_score),
                llm_reasoning=_discovery_trace_to_dict(agent_opp),
            )
            session.add(opp_row)
            session.flush()  # get opp_row.id

            # Write Attempt row (uses the winning patch)
            patch = (
                cycle_result.agent_run.patches[i]
                if i < len(cycle_result.agent_run.patches)
                else None
            )
            attempt_row = Attempt(
                opportunity_id=opp_row.id,
                diff=patch.diff if patch else "",
                validation_result=_candidate_to_dict(candidate),
                status="accepted" if candidate.is_accepted else "rejected",
                llm_reasoning=_patch_trace_to_dict(patch),
            )
            session.add(attempt_row)

            # Only accepted candidates become Proposals
            if candidate.is_accepted and proposals_created < max_proposals:
                decisive = candidate.attempts[-1] if candidate.attempts else None
                metrics_after_dict = (
                    decisive.pipeline_result.to_dict()
                    if decisive and decisive.pipeline_result else None
                )
                # Serialize all patch variants for rich UI display
                variants = (
                    cycle_result.patch_variants_for_candidate[i]
                    if i < len(getattr(cycle_result, "patch_variants_for_candidate", []))
                    else []
                )
                selection_reason = (
                    cycle_result.selection_reasons[i]
                    if i < len(getattr(cycle_result, "selection_reasons", []))
                    else None
                )
                proposal_row = Proposal(
                    run_id=uuid.UUID(run_id),
                    diff=patch.diff if patch else "",
                    summary=agent_opp.rationale or agent_opp.type,
                    risk_score=float(agent_opp.risk_score),
                    confidence=candidate.final_verdict.confidence,
                    metrics_before=_baseline_to_dict(baseline),
                    metrics_after=metrics_after_dict,
                    framework=framework,
                    patch_variants=[v.to_dict() for v in variants] if variants else None,
                    selection_reason=selection_reason,
                    approaches_tried=len(variants) if variants else None,
                    discovery_trace=_discovery_trace_to_dict(agent_opp),
                    patch_trace=_patch_trace_to_dict(patch),
                )
                session.add(proposal_row)
                proposals_created += 1

        session.commit()

    logger.info(
        "Wrote %d proposals for run %s",
        proposals_created, run_id,
    )
    return proposals_created


def _build_seen_signatures(repo_id: uuid.UUID) -> frozenset[tuple[str, str]]:
    """Return all (type, file_path) pairs ever generated for this repo.

    Used to skip opportunities the LLM has already proposed in previous runs,
    regardless of whether they were accepted or declined.
    """
    with get_sync_db() as session:
        rows = session.execute(
            select(Opportunity.type, Opportunity.location)
            .join(Run, Opportunity.run_id == Run.id)
            .where(Run.repo_id == repo_id)
        ).all()
    return frozenset(
        (row.type, row.location.split(":")[0].strip())
        for row in rows
        if row.location
    )


def _discovery_trace_to_dict(opp) -> Optional[dict]:
    """Serialise the AgentOpportunity's discovery trace to a JSON-safe dict."""
    try:
        if opp.thinking_trace:
            return opp.thinking_trace.to_dict()
    except Exception:
        pass
    return None


def _patch_trace_to_dict(patch) -> Optional[dict]:
    """Serialise the AgentPatch's thinking trace to a JSON-safe dict."""
    if patch is None:
        return None
    try:
        if patch.thinking_trace:
            return patch.thinking_trace.to_dict()
    except Exception:
        pass
    return None


def _candidate_to_dict(candidate) -> dict:
    """Serialise a CandidateResult to a JSON-safe dict."""
    try:
        return {
            "is_accepted": candidate.is_accepted,
            "confidence": candidate.final_verdict.confidence,
            "reason": candidate.final_verdict.reason,
            "gates_failed": candidate.final_verdict.gates_failed,
            "attempts": len(candidate.attempts),
        }
    except Exception:
        return {"is_accepted": candidate.is_accepted}


def _baseline_to_dict(baseline) -> dict:
    """Serialise a BaselineResult to a JSON-safe dict."""
    try:
        return baseline.to_dict()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Artifact upload
# ---------------------------------------------------------------------------


def _upload_baseline_artifacts(run_id: str, repo_id: str, baseline) -> None:
    """Bundle baseline artifacts and persist Artifact records to the database.

    For each bundle (baseline.json, logs.txt, trace.json):
      1. Attempt to upload the file content to Supabase Storage.
      2. Write an Artifact row referencing the storage_path (or a
         placeholder path when Supabase is not configured).

    Baseline artifacts are *not* tied to a specific Proposal (they capture
    the project state before any patches), so ``proposal_id`` is NULL.
    This method is best-effort: failures are logged but never propagate to
    the caller — we must not abort the run over an artifact upload error.
    """
    try:
        from runner.packaging.bundler import bundle_artifacts

        bundles = bundle_artifacts(run_id=run_id, repo_id=repo_id, baseline_result=baseline)
    except Exception as exc:
        logger.warning("Artifact bundling failed for run %s: %s", run_id, exc)
        return

    settings = get_settings()
    supabase_configured = bool(settings.supabase_service_key)

    for bundle in bundles:
        storage_path = bundle.storage_path

        # ----------------------------------------------------------------
        # 1. Upload file to Supabase Storage (if configured)
        # ----------------------------------------------------------------
        if supabase_configured:
            try:
                from supabase import create_client

                client = create_client(settings.supabase_url, settings.supabase_service_key)
                client.storage.from_(settings.storage_bucket).upload(
                    storage_path,
                    bundle.content.encode("utf-8"),
                    {"contentType": "application/octet-stream", "upsert": "true"},
                )
                logger.info(
                    "Uploaded artifact %s for run %s to Supabase",
                    bundle.filename, run_id,
                )
            except Exception as exc:
                logger.warning(
                    "Supabase upload failed for %s (run %s): %s",
                    bundle.filename, run_id, exc,
                )
                # Keep the storage_path even on upload failure so the
                # Artifact record can be retried later.

        # ----------------------------------------------------------------
        # 2. Write Artifact row (proposal_id=None → baseline artifact)
        # ----------------------------------------------------------------
        try:
            with get_sync_db() as session:
                from app.db.models import Artifact as ArtifactModel

                artifact = ArtifactModel(
                    proposal_id=None,
                    storage_path=storage_path,
                    type=bundle.artifact_type,
                )
                session.add(artifact)
                session.commit()
                logger.info(
                    "Persisted artifact record %s for run %s (type=%s)",
                    artifact.id, run_id, bundle.artifact_type,
                )
        except Exception as exc:
            logger.warning(
                "Failed to persist artifact record for %s (run %s): %s",
                bundle.filename, run_id, exc,
            )


# ---------------------------------------------------------------------------
# Settings counters
# ---------------------------------------------------------------------------


def _increment_failure_counter(run_id: str, repo_id: str, failure_type: str) -> None:
    """Increment the consecutive failure counter and auto-pause if threshold hit."""
    _SETUP_THRESHOLD = 3
    _FLAKY_THRESHOLD = 5

    with get_sync_db() as session:
        settings = session.get(Settings, uuid.UUID(repo_id))
        if not settings:
            return

        if failure_type == "setup":
            settings.consecutive_setup_failures += 1
            if settings.consecutive_setup_failures >= _SETUP_THRESHOLD:
                settings.paused = True
                logger.warning(
                    "Repo %s auto-paused after %d consecutive setup failures",
                    repo_id, settings.consecutive_setup_failures,
                )
        elif failure_type == "flaky":
            settings.consecutive_flaky_runs += 1
            if settings.consecutive_flaky_runs >= _FLAKY_THRESHOLD:
                settings.paused = True
                logger.warning(
                    "Repo %s auto-paused after %d consecutive flaky runs",
                    repo_id, settings.consecutive_flaky_runs,
                )

        session.commit()


def _update_settings_after_success(repo_id: str) -> None:
    """Reset failure counters and update last_run_at on success."""
    with get_sync_db() as session:
        settings = session.get(Settings, uuid.UUID(repo_id))
        if not settings:
            return
        settings.consecutive_setup_failures = 0
        settings.consecutive_flaky_runs = 0
        settings.last_run_at = datetime.now(timezone.utc)
        session.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_repo_url(
    github_full_name: Optional[str],
    github_repo_id: Optional[int],
    token: Optional[str] = None,
) -> str:
    """Build the HTTPS clone URL for a GitHub repository.

    Prefers the ``owner/repo`` full name when available because GitHub's
    /repositories/:id redirect is not accepted by git-clone.  Falls back to
    the numeric-ID URL so the caller always receives a non-empty string even
    when the column is NULL (repo connected before Phase-17 migration).

    When *token* is provided the URL embeds the GitHub installation token so
    that git-clone can access private repositories without interactive auth.
    """
    if github_full_name:
        if token:
            return f"https://x-access-token:{token}@github.com/{github_full_name}.git"
        return f"https://github.com/{github_full_name}.git"
    if github_repo_id:
        # Fallback: git-clone does NOT support this form in all git versions,
        # but we keep it rather than raising so callers can report a clear error.
        return f"https://github.com/repositories/{github_repo_id}"
    raise ValueError("Repository has neither github_full_name nor github_repo_id")


def _resolve_api_key(provider: str) -> str:
    """Return the API key for the given LLM provider from environment variables."""
    import os

    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    env_var = key_map.get(provider, "")
    return os.environ.get(env_var, "") if env_var else ""


def _no_repo_result(run_id: str) -> dict:
    """Return a structured result for runs that cannot proceed due to missing repo URL."""
    return {
        "baseline_completed": False,
        "agent_skipped": True,
        "reason": "no_github_repo_id",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _cancelled_result(run_id: str) -> dict:
    """Return a structured result for cancelled runs."""
    return {
        "baseline_completed": False,
        "agent_skipped": True,
        "reason": "cancelled",
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _resolve_llm_credentials() -> tuple[str, str, str]:
    """Resolve which LLM provider to use based on available API keys.

    Priority: anthropic > openai > google.
    Returns (provider, model, api_key). api_key is empty string if none found.
    """
    import os

    candidates = [
        ("anthropic", "claude-sonnet-4-5", os.environ.get("ANTHROPIC_API_KEY", "")),
        ("openai", "gpt-4o", os.environ.get("OPENAI_API_KEY", "")),
        ("google", "gemini-2.0-flash", os.environ.get("GOOGLE_API_KEY", "")),
    ]
    for provider, model, key in candidates:
        if key:
            return provider, model, key
    return "anthropic", "claude-sonnet-4-5", ""


# ---------------------------------------------------------------------------
# Async helpers for use in FastAPI routes
# ---------------------------------------------------------------------------


async def async_transition_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    target_status: str,
) -> Run:
    """Transition a run's status with state machine validation.

    Used by FastAPI routes.
    """
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    validate_transition(run.status, target_status)
    run.status = target_status
    await db.flush()
    return run


async def async_enqueue_run(
    db: AsyncSession,
    run: Run,
) -> str:
    """Enqueue a run for background execution via Celery.

    Passes `trace_id` so the worker logs are correlated with the
    originating HTTP request.
    """
    from app.engine.tasks import execute_run

    task = execute_run.delay(str(run.id), trace_id=run.trace_id or "")
    return task.id


async def create_and_enqueue_run(
    db: AsyncSession,
    repo_id: uuid.UUID,
    sha: Optional[str] = None,
    trace_id: str = "",
) -> Run:
    """Create a queued Run row and dispatch it to Celery.

    Shared by the manual trigger endpoint and the auto-run-on-connect flow.
    If Celery is unavailable the run stays queued; the beat scheduler will
    pick it up on the next tick.
    """
    run = Run(repo_id=repo_id, sha=sha, status="queued", trace_id=trace_id)
    db.add(run)
    await db.flush()
    try:
        await async_enqueue_run(db, run)
        logger.info("Enqueued run %s for repo %s", run.id, repo_id)
    except Exception:
        logger.warning(
            "Failed to enqueue Celery task for run %s; run remains queued",
            run.id,
            exc_info=True,
        )
    return run
