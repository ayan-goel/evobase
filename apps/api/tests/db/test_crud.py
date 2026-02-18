"""CRUD integration tests using SQLite async engine.

Verifies create, read, update, and delete operations against
all core models. Each test gets a fresh in-memory database.
"""

import uuid

import pytest
from sqlalchemy import select

from app.db.models import (
    Artifact,
    Attempt,
    Baseline,
    Opportunity,
    Organization,
    Proposal,
    Repository,
    Run,
    Settings,
    User,
)


# ---------------------------------------------------------------------------
# Helper: create a full entity chain for tests that need parent records
# ---------------------------------------------------------------------------

async def create_user(session, email: str = "test@coreloop.local") -> User:
    user = User(id=uuid.uuid4(), email=email)
    session.add(user)
    await session.flush()
    return user


async def create_org(session, owner: User, name: str = "Test Org") -> Organization:
    org = Organization(id=uuid.uuid4(), name=name, owner_id=owner.id)
    session.add(org)
    await session.flush()
    return org


async def create_repo(session, org: Organization) -> Repository:
    repo = Repository(
        id=uuid.uuid4(),
        org_id=org.id,
        github_repo_id=123456789,
        default_branch="main",
        package_manager="npm",
        install_cmd="npm install",
        build_cmd="npm run build",
        test_cmd="npm test",
    )
    session.add(repo)
    await session.flush()
    return repo


async def create_run(session, repo: Repository, status: str = "queued") -> Run:
    run = Run(
        id=uuid.uuid4(),
        repo_id=repo.id,
        sha="abc123def456",
        status=status,
    )
    session.add(run)
    await session.flush()
    return run


async def create_full_chain(session):
    """Create user -> org -> repo -> run and return all entities."""
    user = await create_user(session)
    org = await create_org(session, user)
    repo = await create_repo(session, org)
    run = await create_run(session, repo)
    return user, org, repo, run


# ---------------------------------------------------------------------------
# Repository CRUD
# ---------------------------------------------------------------------------

class TestRepositoryCRUD:
    """CRUD operations for the repositories table."""

    async def test_create_repository(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)
        await db_session.commit()

        result = await db_session.execute(
            select(Repository).where(Repository.id == repo.id)
        )
        fetched = result.scalar_one()

        assert fetched.package_manager == "npm"
        assert fetched.default_branch == "main"
        assert fetched.github_repo_id == 123456789

    async def test_read_repository_by_org(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        await create_repo(db_session, org)
        await db_session.commit()

        result = await db_session.execute(
            select(Repository).where(Repository.org_id == org.id)
        )
        repos = result.scalars().all()
        assert len(repos) == 1

    async def test_update_repository_commands(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)
        await db_session.commit()

        repo.test_cmd = "npm run test:ci"
        await db_session.commit()

        result = await db_session.execute(
            select(Repository).where(Repository.id == repo.id)
        )
        updated = result.scalar_one()
        assert updated.test_cmd == "npm run test:ci"

    async def test_delete_repository(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)
        repo_id = repo.id
        await db_session.commit()

        await db_session.delete(repo)
        await db_session.commit()

        result = await db_session.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Run CRUD + Status Transitions
# ---------------------------------------------------------------------------

class TestRunCRUD:
    """CRUD and state transition tests for the runs table."""

    async def test_create_run_defaults_to_queued(self, db_session):
        _, _, repo, run = await create_full_chain(db_session)
        await db_session.commit()

        assert run.status == "queued"

    async def test_transition_queued_to_running(self, db_session):
        """Verify the run status can transition from queued to running."""
        _, _, repo, run = await create_full_chain(db_session)
        await db_session.commit()

        run.status = "running"
        await db_session.commit()

        result = await db_session.execute(select(Run).where(Run.id == run.id))
        assert result.scalar_one().status == "running"

    async def test_transition_running_to_completed(self, db_session):
        _, _, repo, run = await create_full_chain(db_session)
        run.status = "running"
        await db_session.commit()

        run.status = "completed"
        run.compute_minutes = 3.5
        await db_session.commit()

        result = await db_session.execute(select(Run).where(Run.id == run.id))
        completed = result.scalar_one()
        assert completed.status == "completed"
        assert float(completed.compute_minutes) == 3.5

    async def test_transition_running_to_failed(self, db_session):
        _, _, repo, run = await create_full_chain(db_session)
        run.status = "running"
        await db_session.commit()

        run.status = "failed"
        await db_session.commit()

        result = await db_session.execute(select(Run).where(Run.id == run.id))
        assert result.scalar_one().status == "failed"

    async def test_read_runs_by_repo(self, db_session):
        _, _, repo, _ = await create_full_chain(db_session)
        # Create a second run
        await create_run(db_session, repo, status="running")
        await db_session.commit()

        result = await db_session.execute(
            select(Run).where(Run.repo_id == repo.id)
        )
        runs = result.scalars().all()
        assert len(runs) == 2


# ---------------------------------------------------------------------------
# Proposal CRUD
# ---------------------------------------------------------------------------

class TestProposalCRUD:
    """CRUD operations for the proposals table."""

    async def test_create_proposal(self, db_session):
        _, _, _, run = await create_full_chain(db_session)

        proposal = Proposal(
            id=uuid.uuid4(),
            run_id=run.id,
            diff="--- a/src/utils.ts\n+++ b/src/utils.ts\n@@ -1 +1 @@\n-old\n+new",
            summary="Replace Array.includes with Set for O(1) lookup",
            metrics_before={"avg_latency_ms": 120},
            metrics_after={"avg_latency_ms": 110},
            risk_score=0.2,
        )
        db_session.add(proposal)
        await db_session.commit()

        result = await db_session.execute(
            select(Proposal).where(Proposal.id == proposal.id)
        )
        fetched = result.scalar_one()
        assert fetched.summary == "Replace Array.includes with Set for O(1) lookup"
        assert fetched.pr_url is None

    async def test_update_proposal_pr_url(self, db_session):
        """Simulate user clicking 'Create PR' which sets pr_url."""
        _, _, _, run = await create_full_chain(db_session)

        proposal = Proposal(
            id=uuid.uuid4(),
            run_id=run.id,
            diff="diff content",
            summary="Test optimization",
        )
        db_session.add(proposal)
        await db_session.commit()

        proposal.pr_url = "https://github.com/org/repo/pull/42"
        await db_session.commit()

        result = await db_session.execute(
            select(Proposal).where(Proposal.id == proposal.id)
        )
        assert result.scalar_one().pr_url == "https://github.com/org/repo/pull/42"

    async def test_read_proposals_by_run(self, db_session):
        _, _, _, run = await create_full_chain(db_session)

        for i in range(3):
            db_session.add(Proposal(
                id=uuid.uuid4(),
                run_id=run.id,
                diff=f"diff {i}",
                summary=f"Optimization {i}",
            ))
        await db_session.commit()

        result = await db_session.execute(
            select(Proposal).where(Proposal.run_id == run.id)
        )
        assert len(result.scalars().all()) == 3


# ---------------------------------------------------------------------------
# Artifact CRUD
# ---------------------------------------------------------------------------

class TestArtifactCRUD:
    """CRUD operations for the artifacts table."""

    async def test_create_artifact(self, db_session):
        _, _, _, run = await create_full_chain(db_session)

        proposal = Proposal(
            id=uuid.uuid4(),
            run_id=run.id,
            diff="diff content",
            summary="Test",
        )
        db_session.add(proposal)
        await db_session.flush()

        artifact = Artifact(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            storage_path="artifacts/repos/abc/runs/def/logs.txt",
            type="log",
        )
        db_session.add(artifact)
        await db_session.commit()

        result = await db_session.execute(
            select(Artifact).where(Artifact.id == artifact.id)
        )
        fetched = result.scalar_one()
        assert fetched.type == "log"
        assert "logs.txt" in fetched.storage_path

    async def test_read_artifacts_by_proposal(self, db_session):
        _, _, _, run = await create_full_chain(db_session)

        proposal = Proposal(
            id=uuid.uuid4(),
            run_id=run.id,
            diff="diff",
            summary="Test",
        )
        db_session.add(proposal)
        await db_session.flush()

        artifact_types = ["log", "trace", "bench", "diff"]
        for atype in artifact_types:
            db_session.add(Artifact(
                id=uuid.uuid4(),
                proposal_id=proposal.id,
                storage_path=f"artifacts/repos/x/runs/y/{atype}.json",
                type=atype,
            ))
        await db_session.commit()

        result = await db_session.execute(
            select(Artifact).where(Artifact.proposal_id == proposal.id)
        )
        artifacts = result.scalars().all()
        assert len(artifacts) == 4
        assert {a.type for a in artifacts} == {"log", "trace", "bench", "diff"}


# ---------------------------------------------------------------------------
# Cascade deletion tests
# ---------------------------------------------------------------------------

class TestCascadeDeletion:
    """Verify that cascade deletes propagate correctly through the entity chain."""

    async def test_deleting_user_cascades_to_org_and_repo(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)
        repo_id = repo.id
        await db_session.commit()

        await db_session.delete(user)
        await db_session.commit()

        result = await db_session.execute(
            select(Repository).where(Repository.id == repo_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_deleting_run_cascades_to_proposals_and_artifacts(self, db_session):
        _, _, _, run = await create_full_chain(db_session)
        run_id = run.id

        proposal = Proposal(
            id=uuid.uuid4(),
            run_id=run.id,
            diff="diff",
            summary="Test",
        )
        db_session.add(proposal)
        await db_session.flush()

        artifact = Artifact(
            id=uuid.uuid4(),
            proposal_id=proposal.id,
            storage_path="artifacts/test/log.txt",
            type="log",
        )
        db_session.add(artifact)
        artifact_id = artifact.id
        await db_session.commit()

        await db_session.delete(run)
        await db_session.commit()

        result = await db_session.execute(
            select(Artifact).where(Artifact.id == artifact_id)
        )
        assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Settings CRUD
# ---------------------------------------------------------------------------

class TestSettingsCRUD:
    """CRUD for the per-repo settings table."""

    async def test_create_settings(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)

        settings = Settings(
            repo_id=repo.id,
            compute_budget_minutes=120,
            max_proposals_per_run=5,
            schedule="0 3 * * *",
        )
        db_session.add(settings)
        await db_session.commit()

        result = await db_session.execute(
            select(Settings).where(Settings.repo_id == repo.id)
        )
        fetched = result.scalar_one()
        assert fetched.compute_budget_minutes == 120
        assert fetched.schedule == "0 3 * * *"

    async def test_update_settings_budget(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)

        settings = Settings(
            repo_id=repo.id,
            compute_budget_minutes=60,
            max_proposals_per_run=10,
            schedule="0 2 * * *",
        )
        db_session.add(settings)
        await db_session.commit()

        settings.compute_budget_minutes = 30
        await db_session.commit()

        result = await db_session.execute(
            select(Settings).where(Settings.repo_id == repo.id)
        )
        assert result.scalar_one().compute_budget_minutes == 30


# ---------------------------------------------------------------------------
# Baseline CRUD
# ---------------------------------------------------------------------------

class TestBaselineCRUD:
    """CRUD operations for baselines."""

    async def test_create_baseline_with_metrics(self, db_session):
        user = await create_user(db_session)
        org = await create_org(db_session, user)
        repo = await create_repo(db_session, org)

        baseline = Baseline(
            id=uuid.uuid4(),
            repo_id=repo.id,
            sha="abc123",
            metrics={"test_count": 42, "build_time_ms": 5000},
            environment_fingerprint={"node": "20.11.0", "os": "linux"},
        )
        db_session.add(baseline)
        await db_session.commit()

        result = await db_session.execute(
            select(Baseline).where(Baseline.repo_id == repo.id)
        )
        fetched = result.scalar_one()
        assert fetched.sha == "abc123"
        assert fetched.metrics["test_count"] == 42


# ---------------------------------------------------------------------------
# Opportunity + Attempt chain
# ---------------------------------------------------------------------------

class TestOpportunityAttemptCRUD:
    """CRUD operations for opportunities and attempts."""

    async def test_create_opportunity_and_attempt(self, db_session):
        _, _, _, run = await create_full_chain(db_session)

        opp = Opportunity(
            id=uuid.uuid4(),
            run_id=run.id,
            type="set_membership_swap",
            location="src/utils.ts:42",
            rationale="Array.includes in hot path can be replaced with Set.has",
            risk_score=0.1,
        )
        db_session.add(opp)
        await db_session.flush()

        attempt = Attempt(
            id=uuid.uuid4(),
            opportunity_id=opp.id,
            diff="--- a/src/utils.ts\n+++ b/src/utils.ts",
            validation_result={"build": "pass", "tests": "pass", "bench_delta_pct": 5.2},
            status="accepted",
        )
        db_session.add(attempt)
        await db_session.commit()

        result = await db_session.execute(
            select(Attempt).where(Attempt.opportunity_id == opp.id)
        )
        fetched = result.scalar_one()
        assert fetched.status == "accepted"
        assert fetched.validation_result["bench_delta_pct"] == 5.2

    async def test_rejected_attempt(self, db_session):
        _, _, _, run = await create_full_chain(db_session)

        opp = Opportunity(
            id=uuid.uuid4(),
            run_id=run.id,
            type="memoize_pure_fn",
            location="src/compute.ts:10",
        )
        db_session.add(opp)
        await db_session.flush()

        attempt = Attempt(
            id=uuid.uuid4(),
            opportunity_id=opp.id,
            diff="diff content",
            validation_result={"build": "pass", "tests": "fail", "reason": "assertion error"},
            status="rejected",
        )
        db_session.add(attempt)
        await db_session.commit()

        result = await db_session.execute(
            select(Attempt).where(Attempt.opportunity_id == opp.id)
        )
        fetched = result.scalar_one()
        assert fetched.status == "rejected"
        assert fetched.validation_result["tests"] == "fail"
