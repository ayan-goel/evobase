"""Types for the scanner module.

An Opportunity represents a detected optimization candidate
with location, rationale, and risk estimate.
"""

from dataclasses import dataclass, field


# Opportunity types — each maps to a potential patch template in Phase 8.
OPPORTUNITY_TYPES = {
    "set_membership",       # Array.indexOf/includes -> Set.has
    "json_parse_cache",     # Repeated JSON.parse on same string
    "memoize_pure",         # Pure function called repeatedly with same args
    "loop_intermediate",    # Intermediate array allocations in hot loops
    "dead_code",            # Unreachable or unused code
    "redundant_spread",     # Unnecessary object spread in loops
    "string_concat_loop",   # String concatenation in loops (use join)
    "sync_fs_in_handler",   # Synchronous fs calls in request handlers
    "unindexed_find",       # Array.find in hot path (could use Map)
    "regex_in_loop",        # Regex compilation inside loops
}


@dataclass
class Opportunity:
    """A detected optimization opportunity.

    type: One of the OPPORTUNITY_TYPES identifiers.
    location: File path and line number (e.g., "src/utils.ts:42").
    rationale: Human-readable explanation of why this is an opportunity.
    risk_score: 0.0 (safe) to 1.0 (risky). Lower = safer to optimize.
    source: Which scanner pass detected this ("heuristic" or "ast").
    """

    type: str
    location: str
    rationale: str
    risk_score: float
    source: str

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "location": self.location,
            "rationale": self.rationale,
            "risk_score": round(self.risk_score, 2),
            "source": self.source,
        }


@dataclass
class ScanResult:
    """Complete scanner output for a repository.

    Opportunities are ranked by risk (lowest first = safest).
    """

    opportunities: list[Opportunity] = field(default_factory=list)
    files_scanned: int = 0
    scan_duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "opportunities": [o.to_dict() for o in self.opportunities],
            "opportunity_count": len(self.opportunities),
            "files_scanned": self.files_scanned,
            "scan_duration_seconds": round(self.scan_duration_seconds, 3),
        }
