"""SQLAlchemy 2.0 declarative models mirroring the Supabase-managed schema.

These models are read-only reflections: the SQL migrations in
infra/supabase/migrations/ are the source of truth for the schema.
Models here provide ORM navigation and type-safe query building.

Uses dialect-agnostic types (Uuid, JSON) so models work with both
PostgreSQL (production) and SQLite (tests).
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import BigInteger, Integer, JSON, ForeignKey, Numeric, Text, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    github_id: Mapped[Optional[int]] = mapped_column(unique=True)
    github_login: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    organizations: Mapped[list["Organization"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="organizations")
    repositories: Mapped[list["Repository"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class GitHubInstallation(Base):
    __tablename__ = "github_installations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    installation_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False
    )
    account_login: Mapped[str] = mapped_column(Text, nullable=False)
    account_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    github_repo_id: Mapped[Optional[int]] = mapped_column(unique=True)
    # github_full_name stores "owner/repo" (e.g. "acme/api-service").
    # Used as the HTTPS clone URL: https://github.com/{full_name}.git
    github_full_name: Mapped[Optional[str]] = mapped_column(Text)
    default_branch: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'main'")
    )
    package_manager: Mapped[Optional[str]] = mapped_column(Text)
    framework: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    install_cmd: Mapped[Optional[str]] = mapped_column(Text)
    build_cmd: Mapped[Optional[str]] = mapped_column(Text)
    test_cmd: Mapped[Optional[str]] = mapped_column(Text)
    typecheck_cmd: Mapped[Optional[str]] = mapped_column(Text)
    bench_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    installation_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    # Subdirectory within the repo to run detection and commands from.
    # Set this for monorepos where only one sub-project should be analysed.
    root_dir: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="repositories")
    baselines: Mapped[list["Baseline"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    runs: Mapped[list["Run"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    settings: Mapped[Optional["Settings"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan", uselist=False
    )


class Baseline(Base):
    """Baseline build/test/bench metrics at a specific commit SHA.

    Used as the comparison point for optimization proposals.
    """

    __tablename__ = "baselines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    sha: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    environment_fingerprint: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    repository: Mapped["Repository"] = relationship(back_populates="baselines")


class Run(Base):
    """Optimization cycle run.

    Status follows a strict state machine: queued -> running -> completed | failed.
    All further updates must include run_id for trace correlation.
    """

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    sha: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'queued'")
    )
    compute_minutes: Mapped[Optional[float]] = mapped_column(Numeric, default=0)
    # trace_id links the run to the originating HTTP request (X-Request-ID)
    # and threads through all Celery worker logs for grep-ability.
    trace_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    repository: Mapped["Repository"] = relationship(back_populates="runs")
    opportunities: Mapped[list["Opportunity"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    proposals: Mapped[list["Proposal"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Opportunity(Base):
    """Optimization opportunity identified by the LLM discovery agent.

    llm_reasoning stores the agent's ThinkingTrace as JSON so the UI can
    show the developer exactly why this location was flagged.
    """

    __tablename__ = "opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    risk_score: Mapped[Optional[float]] = mapped_column(Numeric, default=0)
    # LLM discovery agent reasoning trace (ThinkingTrace serialised to JSON)
    llm_reasoning: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    run: Mapped["Run"] = relationship(back_populates="opportunities")
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class Attempt(Base):
    """Patch validation attempt.

    Only accepted attempts become proposals.
    Rejected attempts are logged but never surfaced to users.
    llm_reasoning stores the patch-generation ThinkingTrace as JSON.
    """

    __tablename__ = "attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    validation_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'rejected'")
    )
    # LLM patch-generation agent reasoning trace (ThinkingTrace serialised to JSON)
    llm_reasoning: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    opportunity: Mapped["Opportunity"] = relationship(back_populates="attempts")


class Proposal(Base):
    """Validated optimization proposal with full evidence.

    PR creation is a user-initiated action.
    pr_url is only populated after the user explicitly requests PR creation.
    """

    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    diff: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    metrics_before: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    metrics_after: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    risk_score: Mapped[Optional[float]] = mapped_column(Numeric, default=0)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    pr_url: Mapped[Optional[str]] = mapped_column(Text)

    # confidence is set from the validator's AcceptanceVerdict ("high", "medium", "low")
    confidence: Mapped[Optional[str]] = mapped_column(Text)

    # Denormalized from the run's repository for analytics queries
    framework: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # All patch approach variants tried for this proposal (winner + alternatives)
    patch_variants: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    # Why the winning variant was selected over the alternatives
    selection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # How many approach variants were generated and tested
    approaches_tried: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    discovery_trace: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    patch_trace: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

    run: Mapped["Run"] = relationship(back_populates="proposals")
    artifacts: Mapped[list["Artifact"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )


class Artifact(Base):
    """Metadata for evidence files stored in Supabase Storage.

    Storage paths follow: artifacts/repos/{repo_id}/runs/{run_id}/...
    Files are accessed via signed URLs generated by FastAPI.
    The service role key is used for uploads; never exposed to the frontend.
    """

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    # proposal_id is NULL for baseline artifacts (run-level evidence captured
    # before any patch attempt). It is set for per-proposal artifacts such as
    # diff.patch and agent trace files.
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"), nullable=True
    )
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )

    proposal: Mapped[Optional["Proposal"]] = relationship(back_populates="artifacts")


class Settings(Base):
    """Per-repo budget and scheduling configuration.

    One row per repository. Schedule is a standard cron string.
    Budget limits are enforced at the orchestration layer during run execution.

    Auto-pause: the repo is paused when consecutive_setup_failures >= 3 or
    consecutive_flaky_runs >= 5. Pausing prevents further scheduled runs until
    a human reviews and manually unpauses.
    """

    __tablename__ = "settings"

    repo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    compute_budget_minutes: Mapped[int] = mapped_column(nullable=False, default=60)
    max_proposals_per_run: Mapped[int] = mapped_column(nullable=False, default=10)
    max_candidates_per_run: Mapped[int] = mapped_column(nullable=False, default=20)
    schedule: Mapped[str] = mapped_column(Text, nullable=False, default="0 2 * * *")

    # Auto-pause state
    paused: Mapped[bool] = mapped_column(nullable=False, default=False)
    consecutive_setup_failures: Mapped[int] = mapped_column(nullable=False, default=0)
    consecutive_flaky_runs: Mapped[int] = mapped_column(nullable=False, default=0)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # LLM model selection — user configures which model analyses this repo
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False, default="anthropic")
    llm_model: Mapped[str] = mapped_column(Text, nullable=False, default="claude-sonnet-4-5")

    repository: Mapped["Repository"] = relationship(back_populates="settings")
