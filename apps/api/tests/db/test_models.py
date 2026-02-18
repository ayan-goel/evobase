"""Tests for SQLAlchemy model definitions and table metadata.

Verifies that all 10 models are correctly defined, table names match
the SQL migration, and relationships are properly configured.
"""

from app.db.models import (
    Artifact,
    Attempt,
    Base,
    Baseline,
    GitHubInstallation,
    Opportunity,
    Organization,
    Proposal,
    Repository,
    Run,
    Settings,
    User,
)


class TestModelMetadata:
    """Verify model table names and column definitions match the schema."""

    def test_all_tables_registered(self):
        """All 11 tables must be registered in Base metadata."""
        table_names = set(Base.metadata.tables.keys())
        expected = {
            "users",
            "organizations",
            "github_installations",
            "repositories",
            "baselines",
            "runs",
            "opportunities",
            "attempts",
            "proposals",
            "artifacts",
            "settings",
        }
        assert table_names == expected

    def test_user_table_columns(self):
        table = User.__table__
        column_names = {c.name for c in table.columns}
        assert column_names == {
            "id", "email", "github_id", "github_login", "avatar_url", "created_at",
        }

    def test_organization_table_columns(self):
        table = Organization.__table__
        column_names = {c.name for c in table.columns}
        assert column_names == {"id", "name", "owner_id", "created_at"}

    def test_repository_table_columns(self):
        table = Repository.__table__
        column_names = {c.name for c in table.columns}
        expected = {
            "id",
            "org_id",
            "github_repo_id",
            "github_full_name",
            "default_branch",
            "package_manager",
            "install_cmd",
            "build_cmd",
            "test_cmd",
            "typecheck_cmd",
            "bench_config",
            "installation_id",
            "created_at",
        }
        assert column_names == expected

    def test_github_installations_table_columns(self):
        table = GitHubInstallation.__table__
        column_names = {c.name for c in table.columns}
        expected = {
            "id", "installation_id", "account_login", "account_id",
            "user_id", "created_at",
        }
        assert column_names == expected

    def test_baseline_table_columns(self):
        table = Baseline.__table__
        column_names = {c.name for c in table.columns}
        expected = {"id", "repo_id", "sha", "metrics", "environment_fingerprint", "created_at"}
        assert column_names == expected

    def test_run_table_columns(self):
        table = Run.__table__
        column_names = {c.name for c in table.columns}
        expected = {"id", "repo_id", "sha", "status", "compute_minutes", "trace_id", "created_at"}
        assert column_names == expected

    def test_opportunity_table_columns(self):
        table = Opportunity.__table__
        column_names = {c.name for c in table.columns}
        expected = {
            "id", "run_id", "type", "location", "rationale",
            "risk_score", "llm_reasoning", "created_at",
        }
        assert column_names == expected

    def test_attempt_table_columns(self):
        table = Attempt.__table__
        column_names = {c.name for c in table.columns}
        expected = {
            "id", "opportunity_id", "diff", "validation_result",
            "status", "llm_reasoning", "created_at",
        }
        assert column_names == expected

    def test_proposal_table_columns(self):
        table = Proposal.__table__
        column_names = {c.name for c in table.columns}
        expected = {
            "id",
            "run_id",
            "diff",
            "summary",
            "metrics_before",
            "metrics_after",
            "risk_score",
            "confidence",
            "created_at",
            "pr_url",
            "discovery_trace",
            "patch_trace",
        }
        assert column_names == expected

    def test_artifact_table_columns(self):
        table = Artifact.__table__
        column_names = {c.name for c in table.columns}
        expected = {"id", "proposal_id", "storage_path", "type", "created_at"}
        assert column_names == expected

    def test_settings_table_columns(self):
        table = Settings.__table__
        column_names = {c.name for c in table.columns}
        expected = {
            "repo_id", "compute_budget_minutes", "max_proposals_per_run",
            "max_candidates_per_run", "schedule",
            "paused", "consecutive_setup_failures", "consecutive_flaky_runs", "last_run_at",
            "llm_provider", "llm_model",
        }
        assert column_names == expected

    def test_settings_primary_key_is_repo_id(self):
        """Settings uses repo_id as PK (one settings row per repo)."""
        table = Settings.__table__
        pk_columns = [c.name for c in table.primary_key.columns]
        assert pk_columns == ["repo_id"]


class TestModelRelationships:
    """Verify ORM relationships are configured correctly."""

    def test_user_has_organizations(self):
        assert hasattr(User, "organizations")

    def test_organization_has_owner_and_repositories(self):
        assert hasattr(Organization, "owner")
        assert hasattr(Organization, "repositories")

    def test_repository_has_baselines_runs_settings(self):
        assert hasattr(Repository, "baselines")
        assert hasattr(Repository, "runs")
        assert hasattr(Repository, "settings")

    def test_run_has_opportunities_and_proposals(self):
        assert hasattr(Run, "opportunities")
        assert hasattr(Run, "proposals")

    def test_opportunity_has_attempts(self):
        assert hasattr(Opportunity, "attempts")

    def test_proposal_has_artifacts(self):
        assert hasattr(Proposal, "artifacts")
