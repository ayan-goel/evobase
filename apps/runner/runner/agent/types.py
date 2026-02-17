"""Types for the LLM agent layer.

`AgentOpportunity` and `AgentPatch` are the agent equivalents of the
scanner's `Opportunity` and patchgen's `PatchResult` — but each carries
a `ThinkingTrace` so the reasoning that produced them is preserved.
"""

from dataclasses import dataclass, field
from typing import Optional

from runner.llm.types import ThinkingTrace


@dataclass
class AgentOpportunity:
    """An optimisation opportunity identified by the LLM discovery agent.

    Carries the model's full reasoning trace so the UI can show the
    developer exactly why the agent flagged this location.
    """

    type: str                      # e.g. "performance", "tech_debt"
    location: str                  # "<file>:<line>" (repo-relative)
    rationale: str                 # Why this is a problem
    approach: str                  # What the fix should do
    risk_level: str                # "low" | "medium" | "high"
    affected_lines: int = 0        # Estimated lines the fix will touch
    thinking_trace: Optional[ThinkingTrace] = None  # Discovery reasoning

    @property
    def risk_score(self) -> float:
        """Numeric risk score compatible with the scanner Opportunity type."""
        return {"low": 0.2, "medium": 0.5, "high": 0.8}.get(self.risk_level, 0.5)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "location": self.location,
            "rationale": self.rationale,
            "approach": self.approach,
            "risk_level": self.risk_level,
            "affected_lines": self.affected_lines,
            "risk_score": self.risk_score,
            "thinking_trace": self.thinking_trace.to_dict() if self.thinking_trace else None,
        }


@dataclass
class AgentPatch:
    """A patch produced by the LLM patch-generation agent.

    Structurally equivalent to `PatchResult` but carries additional
    agent metadata. The `diff` field is a unified diff string ready for
    `patch -p1 -f`.
    """

    diff: str
    explanation: str
    touched_files: list[str]
    estimated_lines_changed: int = 0
    thinking_trace: Optional[ThinkingTrace] = None  # Patch generation reasoning

    def to_dict(self) -> dict:
        return {
            "diff": self.diff,
            "explanation": self.explanation,
            "touched_files": self.touched_files,
            "estimated_lines_changed": self.estimated_lines_changed,
            "thinking_trace": self.thinking_trace.to_dict() if self.thinking_trace else None,
        }


@dataclass
class AgentRun:
    """Aggregated output of a full agent cycle for one run.

    Contains all discovered opportunities and their associated patches
    (or failure records when patch generation was not possible).
    """

    opportunities: list[AgentOpportunity] = field(default_factory=list)
    patches: list[Optional[AgentPatch]] = field(default_factory=list)
    # Error messages per opportunity index (None = success)
    errors: list[Optional[str]] = field(default_factory=list)
    model: str = ""
    provider: str = ""

    @property
    def successful_patch_count(self) -> int:
        return sum(1 for p in self.patches if p is not None)
