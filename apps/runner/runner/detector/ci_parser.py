"""GitHub Actions CI workflow parser.

Extracts command signals from .github/workflows/*.yml files.
Parses `run:` steps to identify install, build, test, and typecheck commands.
"""

import logging
from pathlib import Path

import yaml

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Patterns that indicate a specific command category.
# Checked against `run:` step values (case-insensitive).
INSTALL_PATTERNS = ["install", "ci"]
BUILD_PATTERNS = ["build", "compile", "assemble", "package"]
TEST_PATTERNS = [
    "test",
    "spec",
    "jest",
    "vitest",
    "mocha",
    "pytest",
    "rspec",
    "cargo test",
    "go test",
    "mvn test",
    "gradle test",
]
TYPECHECK_PATTERNS = [
    "typecheck",
    "type-check",
    "tsc",
    "mypy",
    "pyright",
    "go vet",
    "cargo clippy",
]

# Package manager indicators found in CI steps
PM_INDICATORS: dict[str, str] = {
    "npm ci": "npm",
    "npm install": "npm",
    "yarn install": "yarn",
    "yarn --frozen-lockfile": "yarn",
    "pnpm install": "pnpm",
    "pnpm/action-setup": "pnpm",
    "bun install": "bun",
    "pip install": "pip",
    "poetry install": "poetry",
    "pipenv install": "pipenv",
    "uv sync": "uv",
    "bundle install": "bundler",
    "go mod download": "go",
    "go mod tidy": "go",
    "cargo fetch": "cargo",
    "mvnw": "maven",
    "mvn ": "maven",
    "gradlew": "gradle",
    "gradle ": "gradle",
}

# Heuristic hints for ecosystem compatibility checks in the orchestrator.
_ECOSYSTEM_HINTS: dict[str, tuple[str, ...]] = {
    "javascript": (
        "npm ",
        "pnpm ",
        "yarn ",
        "bun ",
        "vitest",
        "jest",
        "tsc",
        "node ",
    ),
    "python": (
        "pip ",
        "pipenv ",
        "poetry ",
        "uv ",
        "pytest",
        "python ",
        "mypy",
        "pyright",
    ),
    "ruby": (
        "bundle ",
        "bundler",
        "rspec",
        "rake",
        "rails ",
        "ruby ",
    ),
    "go": ("go ", "gofmt", "golangci"),
    "rust": ("cargo ", "rustc", "clippy"),
    "java": ("mvn", "gradle", "javac", "java ", "kotlinc"),
}


def parse_ci_workflows(repo_dir: Path) -> dict[str, list[CommandSignal]]:
    """Parse all GitHub Actions workflow files and extract command signals.

    Returns a dict mapping categories to lists of signals.
    CI signals have lower confidence than package.json (0.7 vs 0.9)
    since they may include CI-specific commands.
    """
    workflows_dir = repo_dir / ".github" / "workflows"
    if not workflows_dir.exists():
        return {}

    signals: dict[str, list[CommandSignal]] = {}
    workflow_files = list(workflows_dir.glob("*.yml")) + list(
        workflows_dir.glob("*.yaml")
    )

    for wf_path in workflow_files:
        try:
            wf_signals = _parse_single_workflow(wf_path)
            for category, sigs in wf_signals.items():
                signals.setdefault(category, []).extend(sigs)
        except Exception as exc:
            logger.warning("Failed to parse workflow %s: %s", wf_path.name, exc)

    return signals


def _parse_single_workflow(wf_path: Path) -> dict[str, list[CommandSignal]]:
    """Parse a single workflow file for command signals."""
    try:
        content = wf_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        logger.warning("YAML parse error in %s: %s", wf_path.name, exc)
        return {}

    if not isinstance(data, dict):
        return {}

    signals: dict[str, list[CommandSignal]] = {}
    jobs = data.get("jobs", {})

    if not isinstance(jobs, dict):
        return {}

    for job_name, job_config in jobs.items():
        if not isinstance(job_config, dict):
            continue

        steps = job_config.get("steps", [])
        if not isinstance(steps, list):
            continue

        for step_idx, step in enumerate(steps):
            if not isinstance(step, dict):
                continue

            run_cmd = step.get("run", "")
            if not run_cmd:
                # Check for action-based package manager detection
                uses = step.get("uses", "")
                if isinstance(uses, str):
                    for pattern, pm in PM_INDICATORS.items():
                        if pattern in uses:
                            signals.setdefault("package_manager", []).append(
                                CommandSignal(
                                    command=pm,
                                    source=f"ci workflow {wf_path.name} job={job_name} step={step_idx} uses={uses}",
                                    confidence=0.7,
                                )
                            )
                continue

            if not isinstance(run_cmd, str):
                continue

            source = f"ci workflow {wf_path.name} job={job_name} step={step_idx}"
            run_lower = run_cmd.lower().strip()

            # Detect package manager from run commands
            for pattern, pm in PM_INDICATORS.items():
                if pattern in run_lower:
                    signals.setdefault("package_manager", []).append(
                        CommandSignal(command=pm, source=source, confidence=0.7)
                    )

            # Categorize the command
            category = _categorize_command(run_lower)
            if category:
                signals.setdefault(category, []).append(
                    CommandSignal(
                        command=run_cmd.strip(),
                        source=source,
                        confidence=0.7,
                    )
                )

    return signals


def _categorize_command(run_cmd: str) -> str | None:
    """Categorize a CI run command into build/test/typecheck/install.

    Returns the category string or None if no match.
    Checks in order of specificity: typecheck > test > build > install.
    """
    # Typecheck is the most specific — check first
    for pattern in TYPECHECK_PATTERNS:
        if pattern in run_cmd:
            return "typecheck"

    for pattern in TEST_PATTERNS:
        if pattern in run_cmd:
            return "test"

    for pattern in BUILD_PATTERNS:
        if pattern in run_cmd:
            return "build"

    for pattern in INSTALL_PATTERNS:
        if pattern in run_cmd:
            return "install"

    return None


def infer_command_ecosystems(command: str) -> set[str]:
    """Infer likely ecosystem(s) for a command using keyword hints.

    Returns an empty set for generic commands where ecosystem is ambiguous.
    """
    lowered = command.lower()
    inferred = {
        ecosystem
        for ecosystem, hints in _ECOSYSTEM_HINTS.items()
        if any(hint in lowered for hint in hints)
    }
    return inferred
