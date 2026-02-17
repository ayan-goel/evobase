"""Scanner orchestrator — runs all scanner passes and merges results.

This is the public entry point for scanning. It:
1. Collects all JS/TS files in the repo
2. Runs heuristic and AST scanners on each file
3. Deduplicates opportunities (same type + location)
4. Ranks by risk score (lowest first = safest)
5. Returns a ScanResult with all opportunities
"""

import logging
import time
from pathlib import Path

from runner.scanner.ast_scanner import scan_ast
from runner.scanner.heuristics import scan_heuristics
from runner.scanner.types import Opportunity, ScanResult

logger = logging.getLogger(__name__)

# File extensions to scan
SCANNABLE_EXTENSIONS = {".js", ".jsx", ".mjs", ".ts", ".tsx"}

# Directories to skip during file collection
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next",
    "coverage", ".nyc_output", "__pycache__", ".venv",
}

# Maximum file size to scan (256KB). Larger files are skipped.
MAX_FILE_SIZE = 256 * 1024


def scan(repo_dir: Path) -> ScanResult:
    """Run all scanner passes on a repository.

    Collects JS/TS source files, runs heuristic and AST passes,
    deduplicates, and returns a ranked ScanResult.
    """
    repo_dir = Path(repo_dir)
    start = time.monotonic()

    files = _collect_files(repo_dir)
    logger.info("Collected %d scannable files in %s", len(files), repo_dir)

    all_opportunities: list[Opportunity] = []

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Failed to read %s: %s", file_path, exc)
            continue

        # Use relative path for cleaner locations
        try:
            rel_path = file_path.relative_to(repo_dir)
        except ValueError:
            rel_path = file_path

        # Run both scanner passes
        heuristic_opps = scan_heuristics(rel_path, content)
        ast_opps = scan_ast(rel_path, content)

        all_opportunities.extend(heuristic_opps)
        all_opportunities.extend(ast_opps)

    # Deduplicate: same type + location, prefer AST (lower risk, more precise)
    deduped = _deduplicate(all_opportunities)

    # Sort by risk score (safest first)
    deduped.sort(key=lambda o: o.risk_score)

    duration = time.monotonic() - start
    logger.info(
        "Scan complete: %d opportunities from %d files in %.2fs",
        len(deduped), len(files), duration,
    )

    return ScanResult(
        opportunities=deduped,
        files_scanned=len(files),
        scan_duration_seconds=duration,
    )


def _collect_files(repo_dir: Path) -> list[Path]:
    """Collect all scannable JS/TS files in the repo."""
    files: list[Path] = []

    for path in repo_dir.rglob("*"):
        # Skip ignored directories
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        if not path.is_file():
            continue

        if path.suffix not in SCANNABLE_EXTENSIONS:
            continue

        # Skip very large files
        try:
            if path.stat().st_size > MAX_FILE_SIZE:
                logger.debug("Skipping large file: %s", path)
                continue
        except OSError:
            continue

        files.append(path)

    return sorted(files)


def _deduplicate(opportunities: list[Opportunity]) -> list[Opportunity]:
    """Deduplicate opportunities by type + location.

    When both heuristic and AST find the same opportunity,
    prefer the AST result (more precise, lower risk score).
    """
    seen: dict[str, Opportunity] = {}

    for opp in opportunities:
        key = f"{opp.type}:{opp.location}"

        if key not in seen:
            seen[key] = opp
        elif opp.source == "ast":
            # AST is more precise; prefer it
            seen[key] = opp

    return list(seen.values())
