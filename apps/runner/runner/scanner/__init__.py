"""Scanner module for detecting optimization opportunities.

Public API:
    scan(repo_dir) -> ScanResult
"""

from runner.scanner.orchestrator import scan
from runner.scanner.types import Opportunity, ScanResult

__all__ = ["scan", "Opportunity", "ScanResult"]
