"""Repository map builder.

Produces a compact text representation of the repo directory tree that
fits within a single LLM context window. The map gives the agent enough
structural context to make informed file selection decisions without
having to read all files upfront.

Format:
    <indent><name>/ (for directories)
    <indent><name>  [<N> lines] (for files)

Depth is capped at MAX_DEPTH to keep the map manageable for large repos.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Maximum directory depth to include in the map
MAX_DEPTH = 3

# Directories to skip entirely
SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".nuxt",
    "coverage", ".nyc_output", "__pycache__", ".venv", "venv",
    ".tox", ".pytest_cache", ".mypy_cache",
}

# File extensions to include with line counts
SCANNABLE_EXTENSIONS = {
    # JavaScript / TypeScript
    ".js", ".jsx", ".mjs", ".ts", ".tsx", ".cjs",
    # Python
    ".py", ".pyi",
    # Go
    ".go",
    # Rust
    ".rs",
    # Ruby
    ".rb",
    # JVM
    ".java", ".kt", ".scala",
    # C / C++
    ".c", ".cpp", ".h", ".hpp",
    # C#
    ".cs",
    # Swift
    ".swift",
    # Vue / Svelte
    ".vue", ".svelte",
    # PHP
    ".php",
    # Shell
    ".sh",
}

# Extensions to list without line counts (config / docs)
OTHER_EXTENSIONS = {".json", ".yaml", ".yml", ".md", ".toml", ".env.example"}

# Maximum total files to list before truncating
MAX_FILES_IN_MAP = 200


def build_repo_map(repo_dir: Path) -> str:
    """Return a compact directory tree with file line counts.

    Args:
        repo_dir: Absolute path to the repository root.

    Returns:
        A multi-line string suitable for inclusion in an LLM prompt.
    """
    repo_dir = Path(repo_dir)
    lines: list[str] = [f"Repository root: {repo_dir.name}/", ""]

    file_count = 0

    def _walk(path: Path, depth: int, prefix: str) -> None:
        nonlocal file_count
        if depth > MAX_DEPTH:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.name not in (".github",):
                continue

            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                lines.append(f"{prefix}{entry.name}/")
                _walk(entry, depth + 1, prefix + "  ")

            elif entry.is_file():
                if file_count >= MAX_FILES_IN_MAP:
                    if file_count == MAX_FILES_IN_MAP:
                        lines.append(f"{prefix}... (truncated)")
                    file_count += 1
                    continue

                if entry.suffix in SCANNABLE_EXTENSIONS:
                    line_count = _count_lines(entry)
                    lines.append(f"{prefix}{entry.name}  [{line_count} lines]")
                    file_count += 1
                elif entry.suffix in OTHER_EXTENSIONS:
                    lines.append(f"{prefix}{entry.name}")
                    file_count += 1

    _walk(repo_dir, depth=0, prefix="  ")
    return "\n".join(lines)


def _count_lines(path: Path) -> int:
    """Count newline characters in a file efficiently."""
    try:
        text = path.read_bytes()
        return text.count(b"\n") + (1 if text and not text.endswith(b"\n") else 0)
    except OSError:
        return 0
