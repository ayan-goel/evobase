"""Gemfile parser for Ruby framework and test suite detection.

Parses Gemfile line by line — no external parser needed. Handles both
`gem 'name'` and `gem "name"` quoting styles. Ignores comment lines.
"""

import logging
import re
from pathlib import Path

from runner.detector.types import CommandSignal

logger = logging.getLogger(__name__)

# Maps gem names (exact match on the first gem argument) to framework identifiers.
# Ordered by specificity — first match wins.
FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("rails", "rails"),
    ("grape", "grape"),
    ("sinatra", "sinatra"),
    ("hanami", "hanami"),
    ("roda", "roda"),
    ("padrino", "padrino"),
]

# Maps gem names to test commands. rspec-rails takes priority over plain rspec.
TEST_INDICATORS: list[tuple[str, str]] = [
    ("rspec-rails", "bundle exec rspec"),
    ("rspec", "bundle exec rspec"),
    ("minitest", "bundle exec rails test"),
    ("cucumber", "bundle exec cucumber"),
]

# Matches gem declarations: gem 'name' or gem "name", optionally with version/options
_GEM_RE = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"]""")


def _parse_gems(repo_dir: Path) -> list[str]:
    """Return a list of gem names declared in the Gemfile."""
    path = repo_dir / "Gemfile"
    if not path.exists():
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to read Gemfile: %s", exc)
        return []

    gems: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _GEM_RE.match(stripped)
        if match:
            gems.append(match.group(1).lower())
    return gems


def detect_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect Ruby web framework from Gemfile gem declarations."""
    gems = _parse_gems(repo_dir)
    if not gems:
        return None

    gem_set = set(gems)
    for gem_name, framework in FRAMEWORK_INDICATORS:
        if gem_name in gem_set:
            return CommandSignal(
                command=framework,
                source=f"Gemfile gem: {gem_name}",
                confidence=0.9,
            )

    # Gemfile exists but no known framework
    return CommandSignal(
        command="ruby",
        source="Gemfile (no known framework detected)",
        confidence=0.6,
    )


def detect_test_framework(repo_dir: Path) -> CommandSignal | None:
    """Detect test suite from Gemfile and return the appropriate test command."""
    gems = _parse_gems(repo_dir)
    if not gems:
        return None

    gem_set = set(gems)
    for gem_name, test_cmd in TEST_INDICATORS:
        if gem_name in gem_set:
            return CommandSignal(
                command=test_cmd,
                source=f"Gemfile gem: {gem_name}",
                confidence=0.85,
            )
    return None
