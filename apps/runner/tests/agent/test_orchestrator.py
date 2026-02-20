"""Tests for runner/agent/orchestrator.py.

Focuses on the variant selection logic (_select_best_variant) and the
multi-approach loop integration. LLM calls and validation are fully mocked.
"""

from runner.agent.orchestrator import (
    _build_selection_reason,
    _confidence_rank,
    _select_best_variant,
)
from runner.agent.types import AgentOpportunity, AgentPatch, PatchVariantResult
from runner.validator.types import (
    AcceptanceVerdict,
    AttemptRecord,
    BenchmarkComparison,
    CandidateResult,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_verdict(
    accepted: bool,
    confidence: str = CONFIDENCE_MEDIUM,
    improvement_pct: float = 0.0,
    reason: str = "ok",
) -> AcceptanceVerdict:
    bench = None
    if improvement_pct != 0.0:
        bench = BenchmarkComparison(
            baseline_duration_seconds=1.0,
            candidate_duration_seconds=1.0 * (1 - improvement_pct / 100),
            improvement_pct=improvement_pct,
            is_significant=abs(improvement_pct) >= 1.0,
            passes_threshold=improvement_pct >= 3.0,
        )
    return AcceptanceVerdict(
        is_accepted=accepted,
        confidence=confidence,
        reason=reason,
        gates_passed=["test"] if accepted else [],
        gates_failed=[] if accepted else ["test"],
        benchmark_comparison=bench,
    )


def _make_candidate(accepted: bool, confidence: str = CONFIDENCE_MEDIUM, improvement_pct: float = 0.0) -> CandidateResult:
    verdict = _make_verdict(accepted, confidence, improvement_pct)
    attempt = AttemptRecord(
        attempt_number=1,
        patch_applied=True,
        pipeline_result=None,
        verdict=verdict,
    )
    return CandidateResult(
        attempts=[attempt],
        final_verdict=verdict,
        is_accepted=accepted,
    )


def _make_patch() -> AgentPatch:
    return AgentPatch(
        diff="--- a/f.ts\n+++ b/f.ts\n@@ -1 +1 @@\n-x\n+y\n",
        explanation="fix",
        touched_files=["f.ts"],
    )


def _make_variant(
    idx: int,
    description: str,
    accepted: bool,
    confidence: str = CONFIDENCE_MEDIUM,
    improvement_pct: float = 0.0,
) -> PatchVariantResult:
    return PatchVariantResult(
        approach_index=idx,
        approach_description=description,
        patch=_make_patch(),
        candidate_result=_make_candidate(accepted, confidence, improvement_pct),
    )


# ---------------------------------------------------------------------------
# _select_best_variant
# ---------------------------------------------------------------------------

class TestSelectBestVariant:
    def test_empty_variants_returns_minus_one(self) -> None:
        idx, reason = _select_best_variant([])
        assert idx == -1
        assert "no variants" in reason

    def test_all_rejected_returns_minus_one(self) -> None:
        variants = [
            _make_variant(0, "approach A", accepted=False),
            _make_variant(1, "approach B", accepted=False),
        ]
        idx, reason = _select_best_variant(variants)
        assert idx == -1
        assert "no accepted" in reason

    def test_single_accepted_returns_it(self) -> None:
        variants = [_make_variant(0, "approach A", accepted=True)]
        idx, _ = _select_best_variant(variants)
        assert idx == 0

    def test_prefers_accepted_over_rejected(self) -> None:
        variants = [
            _make_variant(0, "approach A", accepted=False),
            _make_variant(1, "approach B", accepted=True),
        ]
        idx, _ = _select_best_variant(variants)
        assert idx == 1

    def test_prefers_high_confidence_over_medium(self) -> None:
        variants = [
            _make_variant(0, "approach A", accepted=True, confidence=CONFIDENCE_MEDIUM),
            _make_variant(1, "approach B", accepted=True, confidence=CONFIDENCE_HIGH),
        ]
        idx, reason = _select_best_variant(variants)
        assert idx == 1
        assert "high confidence" in reason

    def test_prefers_medium_over_low_confidence(self) -> None:
        variants = [
            _make_variant(0, "approach A", accepted=True, confidence=CONFIDENCE_LOW),
            _make_variant(1, "approach B", accepted=True, confidence=CONFIDENCE_MEDIUM),
        ]
        idx, _ = _select_best_variant(variants)
        assert idx == 1

    def test_prefers_better_benchmark_among_same_confidence(self) -> None:
        variants = [
            _make_variant(0, "approach A", accepted=True, confidence=CONFIDENCE_HIGH, improvement_pct=3.0),
            _make_variant(1, "approach B", accepted=True, confidence=CONFIDENCE_HIGH, improvement_pct=9.5),
        ]
        idx, reason = _select_best_variant(variants)
        assert idx == 1
        assert "9.5%" in reason

    def test_high_confidence_beats_better_benchmark_at_lower_confidence(self) -> None:
        variants = [
            _make_variant(0, "approach A", accepted=True, confidence=CONFIDENCE_MEDIUM, improvement_pct=20.0),
            _make_variant(1, "approach B", accepted=True, confidence=CONFIDENCE_HIGH, improvement_pct=0.0),
        ]
        idx, _ = _select_best_variant(variants)
        assert idx == 1

    def test_marks_winner_flag(self) -> None:
        variants = [
            _make_variant(0, "A", accepted=True, confidence=CONFIDENCE_MEDIUM),
            _make_variant(1, "B", accepted=True, confidence=CONFIDENCE_HIGH),
        ]
        winner_idx, reason = _select_best_variant(variants)
        assert winner_idx == 1

    def test_reason_mentions_rejected_count(self) -> None:
        variants = [
            _make_variant(0, "A", accepted=False),
            _make_variant(1, "B", accepted=False),
            _make_variant(2, "C", accepted=True, confidence=CONFIDENCE_MEDIUM),
        ]
        _, reason = _select_best_variant(variants)
        assert "rejected" in reason


# ---------------------------------------------------------------------------
# _confidence_rank
# ---------------------------------------------------------------------------

class TestConfidenceRank:
    def test_high_returns_2(self) -> None:
        c = _make_candidate(True, CONFIDENCE_HIGH)
        assert _confidence_rank(c) == 2

    def test_medium_returns_1(self) -> None:
        c = _make_candidate(True, CONFIDENCE_MEDIUM)
        assert _confidence_rank(c) == 1

    def test_low_returns_0(self) -> None:
        c = _make_candidate(True, CONFIDENCE_LOW)
        assert _confidence_rank(c) == 0

    def test_no_verdict_returns_0(self) -> None:
        c = CandidateResult(attempts=[], final_verdict=None, is_accepted=False)
        assert _confidence_rank(c) == 0


# ---------------------------------------------------------------------------
# _build_selection_reason
# ---------------------------------------------------------------------------

class TestBuildSelectionReason:
    def test_high_confidence_in_reason(self) -> None:
        v = _make_variant(0, "A", accepted=True, confidence=CONFIDENCE_HIGH)
        reason = _build_selection_reason(v, 1, 1)
        assert "high confidence" in reason

    def test_benchmark_improvement_in_reason(self) -> None:
        v = _make_variant(0, "A", accepted=True, confidence=CONFIDENCE_HIGH, improvement_pct=7.2)
        reason = _build_selection_reason(v, 1, 1)
        assert "7.2%" in reason

    def test_rejected_count_in_reason(self) -> None:
        v = _make_variant(0, "A", accepted=True, confidence=CONFIDENCE_MEDIUM)
        reason = _build_selection_reason(v, 1, 3)
        assert "rejected" in reason

    def test_no_verdict_returns_fallback(self) -> None:
        v = PatchVariantResult(
            approach_index=0,
            approach_description="A",
            patch=_make_patch(),
            candidate_result=CandidateResult(attempts=[], final_verdict=None, is_accepted=False),
        )
        reason = _build_selection_reason(v, 1, 1)
        assert reason == "accepted approach"
