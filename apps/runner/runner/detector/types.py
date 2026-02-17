"""Shared types for the detector module.

All detector outputs conform to DetectionResult, which carries
the detected configuration along with confidence and evidence.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandSignal:
    """A detected command with its source and confidence.

    Source tracks where the signal came from (e.g., "package.json scripts",
    "ci workflow step 3") for debugging and evidence reporting.
    """

    command: str
    source: str
    confidence: float  # 0.0 to 1.0


@dataclass
class DetectionResult:
    """Complete detection output for a repository.

    This is the single JSON-serializable config object the detector produces.
    Confidence is the minimum confidence across all detected fields.
    Evidence lists every signal that contributed to the result.
    """

    package_manager: Optional[str] = None
    install_cmd: Optional[str] = None
    build_cmd: Optional[str] = None
    test_cmd: Optional[str] = None
    typecheck_cmd: Optional[str] = None
    bench_cmd: Optional[str] = None
    framework: Optional[str] = None
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "package_manager": self.package_manager,
            "install_cmd": self.install_cmd,
            "build_cmd": self.build_cmd,
            "test_cmd": self.test_cmd,
            "typecheck_cmd": self.typecheck_cmd,
            "bench_cmd": self.bench_cmd,
            "framework": self.framework,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }
