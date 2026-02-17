"""Unit tests for the CI workflow parser.

Tests YAML parsing, command categorization, package manager detection,
and various edge cases (malformed YAML, empty files, etc.).
"""

from pathlib import Path

import pytest

from runner.detector.ci_parser import (
    _categorize_command,
    parse_ci_workflows,
)


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temp repo with .github/workflows directory."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    return tmp_path


def _write_workflow(tmp_repo: Path, filename: str, content: str) -> None:
    wf_dir = tmp_repo / ".github" / "workflows"
    (wf_dir / filename).write_text(content)


class TestParseCiWorkflows:
    def test_extracts_build_step(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm run build
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "build" in signals
        assert signals["build"][0].command == "npm run build"

    def test_extracts_test_step(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: npm test
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "test" in signals

    def test_extracts_typecheck_step(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm run typecheck
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "typecheck" in signals

    def test_detects_pnpm_from_action(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: pnpm/action-setup@v2
        with:
          version: 8
      - run: pnpm install
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "package_manager" in signals
        pm_commands = [s.command for s in signals["package_manager"]]
        assert "pnpm" in pm_commands

    def test_detects_npm_from_install_step(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm ci
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "package_manager" in signals
        assert signals["package_manager"][0].command == "npm"

    def test_detects_yarn_from_install_step(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: yarn install --frozen-lockfile
      - run: yarn test
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "package_manager" in signals
        pm_commands = [s.command for s in signals["package_manager"]]
        assert "yarn" in pm_commands

    def test_confidence_is_0_7(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: npm test
""")
        signals = parse_ci_workflows(tmp_repo)
        assert signals["test"][0].confidence == 0.7

    def test_source_includes_workflow_name(self, tmp_repo):
        _write_workflow(tmp_repo, "deploy.yml", """
name: Deploy
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm run build
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "deploy.yml" in signals["build"][0].source

    def test_multiple_workflow_files(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: npm test
""")
        _write_workflow(tmp_repo, "build.yml", """
name: Build
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm run build
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "test" in signals
        assert "build" in signals

    def test_no_workflows_dir_returns_empty(self, tmp_path):
        signals = parse_ci_workflows(tmp_path)
        assert signals == {}


class TestYamlEdgeCases:
    """Edge cases for YAML parsing robustness."""

    def test_empty_workflow_file(self, tmp_repo):
        _write_workflow(tmp_repo, "empty.yml", "")
        signals = parse_ci_workflows(tmp_repo)
        assert signals == {}

    def test_malformed_yaml(self, tmp_repo):
        _write_workflow(tmp_repo, "bad.yml", "{{invalid yaml}}")
        signals = parse_ci_workflows(tmp_repo)
        assert signals == {}

    def test_yaml_with_no_jobs(self, tmp_repo):
        _write_workflow(tmp_repo, "minimal.yml", """
name: Minimal
on: push
""")
        signals = parse_ci_workflows(tmp_repo)
        assert signals == {}

    def test_yaml_with_empty_jobs(self, tmp_repo):
        _write_workflow(tmp_repo, "empty-jobs.yml", """
name: Empty
on: push
jobs:
""")
        signals = parse_ci_workflows(tmp_repo)
        assert signals == {}

    def test_yaml_with_non_dict_jobs(self, tmp_repo):
        _write_workflow(tmp_repo, "list-jobs.yml", """
name: Bad
on: push
jobs:
  - not-a-dict
""")
        signals = parse_ci_workflows(tmp_repo)
        assert signals == {}

    def test_step_without_run_or_uses(self, tmp_repo):
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: just a name
""")
        signals = parse_ci_workflows(tmp_repo)
        # No run command means no signals
        assert "build" not in signals

    def test_yaml_file_extension(self, tmp_repo):
        """Both .yml and .yaml extensions should be parsed."""
        _write_workflow(tmp_repo, "ci.yaml", """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: npm test
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "test" in signals

    def test_multiline_run_command(self, tmp_repo):
        """Multi-line run commands should be handled."""
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: |
          npm ci
          npm run build
""")
        signals = parse_ci_workflows(tmp_repo)
        # The multi-line block should match both install and build
        assert "install" in signals or "build" in signals

    def test_matrix_strategy_workflow(self, tmp_repo):
        """Workflows with matrix strategies should parse correctly."""
        _write_workflow(tmp_repo, "ci.yml", """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20]
    steps:
      - run: npm test
""")
        signals = parse_ci_workflows(tmp_repo)
        assert "test" in signals


class TestCategorizeCommand:
    def test_build(self):
        assert _categorize_command("npm run build") == "build"

    def test_test(self):
        assert _categorize_command("npm test") == "test"

    def test_jest(self):
        assert _categorize_command("npx jest --coverage") == "test"

    def test_vitest(self):
        assert _categorize_command("npx vitest run") == "test"

    def test_mocha(self):
        assert _categorize_command("mocha --recursive") == "test"

    def test_typecheck(self):
        assert _categorize_command("npm run typecheck") == "typecheck"

    def test_tsc(self):
        assert _categorize_command("tsc --noEmit") == "typecheck"

    def test_install_npm(self):
        assert _categorize_command("npm ci") == "install"

    def test_install_yarn(self):
        assert _categorize_command("yarn install") == "install"

    def test_unknown_command(self):
        assert _categorize_command("echo hello") is None

    def test_typecheck_has_priority_over_test(self):
        """A command mentioning both 'test' and 'typecheck' is typecheck."""
        assert _categorize_command("npm run typecheck -- test") == "typecheck"

    def test_compile_matches_build(self):
        assert _categorize_command("npm run compile") == "build"
