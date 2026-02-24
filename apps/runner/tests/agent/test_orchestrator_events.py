"""Event emission tests for runner/agent/orchestrator.py."""

from unittest.mock import MagicMock

from runner.agent.orchestrator import run_agent_cycle
from runner.agent.patchgen import PatchGenTryRecord, PatchGenerationOutcome
from runner.agent.types import AgentOpportunity, AgentPatch
from runner.detector.types import DetectionResult
from runner.llm.types import LLMConfig, ThinkingTrace
from runner.validator.types import (
    AcceptanceVerdict,
    AttemptRecord,
    BaselineResult,
    BenchmarkComparison,
    CandidateResult,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    StepResult,
)


def _make_llm_config() -> LLMConfig:
    return LLMConfig(provider="anthropic", model="claude-sonnet-4-5", api_key="test")


def _make_trace(reasoning: str = "trace") -> ThinkingTrace:
    return ThinkingTrace(
        model="claude-sonnet-4-5",
        provider="anthropic",
        reasoning=reasoning,
        prompt_tokens=100,
        completion_tokens=50,
    )


def _make_opportunity() -> AgentOpportunity:
    return AgentOpportunity(
        type="performance",
        location="src/ui.tsx:42",
        rationale="Avoid repeated heavy computation on every render",
        risk_level="low",
        approaches=["Memoize the derived view model and hoist stable transforms."],
        affected_lines=8,
        thinking_trace=_make_trace("discovery trace"),
    )


def _make_patch() -> AgentPatch:
    return AgentPatch(
        diff="--- a/src/ui.tsx\n+++ b/src/ui.tsx\n@@ -1 +1 @@\n-x\n+y\n",
        explanation="Memoizes the derived value to avoid repeated work.",
        touched_files=["src/ui.tsx"],
        estimated_lines_changed=2,
        thinking_trace=_make_trace("patch trace"),
    )


def _make_candidate_result() -> CandidateResult:
    steps = [
        StepResult(
            name="build",
            command="npm run build",
            exit_code=0,
            duration_seconds=1.25,
            stdout="ok\n",
            stderr="",
        ),
        StepResult(
            name="test",
            command="npm run test",
            exit_code=0,
            duration_seconds=2.5,
            stdout="ok\n",
            stderr="",
        ),
    ]
    bench = BenchmarkComparison(
        baseline_duration_seconds=1.0,
        candidate_duration_seconds=0.92,
        improvement_pct=8.0,
        is_significant=True,
        passes_threshold=True,
    )
    verdict = AcceptanceVerdict(
        is_accepted=True,
        confidence="high",
        reason="Build and tests pass; benchmark improves materially.",
        gates_passed=["test_gate", "bench_gate"],
        gates_failed=[],
        benchmark_comparison=bench,
    )
    attempt = AttemptRecord(
        attempt_number=1,
        patch_applied=True,
        pipeline_result=BaselineResult(steps=steps, is_success=True),
        verdict=verdict,
        error=None,
    )
    return CandidateResult(
        attempts=[attempt],
        final_verdict=verdict,
        is_accepted=True,
    )


async def test_emits_enriched_patch_and_validation_event_payloads(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = _make_opportunity()
    patch = _make_patch()
    patch_outcome = PatchGenerationOutcome(
        success=True,
        patch=patch,
        tries=[
            PatchGenTryRecord(
                attempt_number=1,
                success=True,
                patch=patch,
                patch_trace=patch.thinking_trace,
            )
        ],
    )
    candidate_result = _make_candidate_result()

    async def fake_discover_opportunities(**kwargs):
        return [opp]

    async def fake_generate_patch_with_diagnostics(**kwargs):
        return patch_outcome

    def fake_run_candidate_validation(**kwargs):
        return candidate_result

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover_opportunities)
    monkeypatch.setattr(
        "runner.agent.orchestrator.generate_agent_patch_with_diagnostics",
        fake_generate_patch_with_diagnostics,
    )
    monkeypatch.setattr("runner.agent.orchestrator.run_candidate_validation", fake_run_candidate_validation)

    emitted: list[tuple[str, str, dict]] = []
    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(build_cmd="npm run build", test_cmd="npm run test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=1,
        on_event=lambda et, ph, data: emitted.append((et, ph, data)),
    )

    assert result.total_attempted == 1

    started = next(e for e in emitted if e[0] == "patch.approach.started")[2]
    assert started["approach_desc_full"] == opp.approaches[0]
    assert started["rationale"] == opp.rationale
    assert started["risk_level"] == "low"
    assert started["affected_lines"] == 8

    completed = next(e for e in emitted if e[0] == "patch.approach.completed")[2]
    assert completed["success"] is True
    assert completed["location"] == opp.location
    assert completed["type"] == opp.type
    assert completed["approach_desc_full"] == opp.approaches[0]
    assert completed["diff"].startswith("--- a/src/ui.tsx")
    assert completed["explanation"] == patch.explanation
    assert completed["patch_trace"]["reasoning"] == "patch trace"
    assert len(completed["patchgen_tries"]) == 1
    assert completed["patchgen_tries"][0]["success"] is True
    assert completed["patchgen_tries"][0]["diff"].startswith("--- a/src/ui.tsx")

    verdict = next(e for e in emitted if e[0] == "validation.verdict")[2]
    assert verdict["attempts"]
    attempt0 = verdict["attempts"][0]
    assert attempt0["patch_applied"] is True
    assert attempt0["steps"][0]["command"] == "npm run build"
    assert attempt0["steps"][0]["stdout_lines"] == 2
    assert attempt0["steps"][1]["name"] == "test"
    assert verdict["benchmark_comparison"]["improvement_pct"] == 8.0


async def test_emits_patch_failure_diagnostics_when_patchgen_returns_none(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = _make_opportunity()
    failed_try_trace = _make_trace("patch parse trace")
    patch_outcome = PatchGenerationOutcome(
        success=False,
        patch=None,
        failure_stage="json_parse",
        failure_reason="Expecting value: line 1 column 1 (char 0)",
        tries=[
            PatchGenTryRecord(
                attempt_number=1,
                success=False,
                failure_stage="json_parse",
                failure_reason="Expecting value: line 1 column 1 (char 0)",
                patch=None,
                patch_trace=failed_try_trace,
            )
        ],
    )

    async def fake_discover_opportunities(**kwargs):
        return [opp]

    async def fake_generate_patch_with_diagnostics(**kwargs):
        return patch_outcome

    def should_not_run_validation(**kwargs):
        raise AssertionError("run_candidate_validation should not be called when patch generation fails")

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover_opportunities)
    monkeypatch.setattr(
        "runner.agent.orchestrator.generate_agent_patch_with_diagnostics",
        fake_generate_patch_with_diagnostics,
    )
    monkeypatch.setattr("runner.agent.orchestrator.run_candidate_validation", should_not_run_validation)

    emitted: list[tuple[str, str, dict]] = []
    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm run test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=1,
        on_event=lambda et, ph, data: emitted.append((et, ph, data)),
    )

    assert result.total_attempted == 1

    completed = next(e for e in emitted if e[0] == "patch.approach.completed")[2]
    assert completed["success"] is False
    assert completed["failure_stage"] == "json_parse"
    assert "Expecting value" in completed["failure_reason"]
    assert completed["patch_trace"]["reasoning"] == "patch parse trace"
    assert len(completed["patchgen_tries"]) == 1
    assert completed["patchgen_tries"][0]["failure_stage"] == "json_parse"

    verdict = next(e for e in emitted if e[0] == "validation.verdict")[2]
    assert isinstance(verdict["attempts"], list)
    assert verdict["attempts"][0]["steps"] == []


# ---------------------------------------------------------------------------
# Smart lazy stopping: high-confidence breaks early; medium does not
# ---------------------------------------------------------------------------

def _make_outcome(patch: AgentPatch) -> PatchGenerationOutcome:
    return PatchGenerationOutcome(
        success=True,
        patch=patch,
        tries=[PatchGenTryRecord(attempt_number=1, success=True, patch=patch, patch_trace=patch.thinking_trace)],
    )


def _make_simple_candidate(confidence: str, accepted: bool = True) -> CandidateResult:
    verdict = AcceptanceVerdict(
        is_accepted=accepted,
        confidence=confidence,
        reason="ok",
        gates_passed=["test"] if accepted else [],
        gates_failed=[] if accepted else ["test"],
        benchmark_comparison=None,
    )
    attempt = AttemptRecord(attempt_number=1, patch_applied=True, pipeline_result=None, verdict=verdict)
    return CandidateResult(attempts=[attempt], final_verdict=verdict, is_accepted=accepted)


async def test_high_confidence_stops_after_first_approach(monkeypatch, tmp_path):
    """A high-confidence accepted variant should short-circuit; no further approaches tried."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = AgentOpportunity(
        type="performance",
        location="src/ui.tsx:1",
        rationale="reason",
        risk_level="low",
        approaches=["approach A", "approach B", "approach C"],
        affected_lines=2,
        thinking_trace=_make_trace(),
    )
    patch = _make_patch()

    async def fake_discover(**kw):
        return [opp]

    async def fake_patchgen(**kw):
        return _make_outcome(patch)

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover)
    monkeypatch.setattr("runner.agent.orchestrator.generate_agent_patch_with_diagnostics", fake_patchgen)
    monkeypatch.setattr(
        "runner.agent.orchestrator.run_candidate_validation",
        lambda **kw: _make_simple_candidate(CONFIDENCE_HIGH),
    )

    emitted: list[tuple[str, str, dict]] = []
    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=5,
        on_event=lambda et, ph, data: emitted.append((et, ph, data)),
    )

    approaches_tried = next(e for e in emitted if e[0] == "validation.verdict")[2]["approaches_tried"]
    assert approaches_tried == 1, "High-confidence should stop after the first approach"


async def test_medium_confidence_continues_to_next_approach(monkeypatch, tmp_path):
    """A medium-confidence accepted variant should NOT stop the loop; approach 2 gets tried."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = AgentOpportunity(
        type="performance",
        location="src/ui.tsx:1",
        rationale="reason",
        risk_level="low",
        approaches=["approach A", "approach B"],
        affected_lines=2,
        thinking_trace=_make_trace(),
    )
    patch = _make_patch()

    call_count = {"n": 0}

    async def fake_discover(**kw):
        return [opp]

    async def fake_patchgen(**kw):
        return _make_outcome(patch)

    def fake_validate(**kw):
        call_count["n"] += 1
        return _make_simple_candidate(CONFIDENCE_MEDIUM)

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover)
    monkeypatch.setattr("runner.agent.orchestrator.generate_agent_patch_with_diagnostics", fake_patchgen)
    monkeypatch.setattr("runner.agent.orchestrator.run_candidate_validation", fake_validate)

    emitted: list[tuple[str, str, dict]] = []
    await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=5,
        on_event=lambda et, ph, data: emitted.append((et, ph, data)),
    )

    approaches_tried = next(e for e in emitted if e[0] == "validation.verdict")[2]["approaches_tried"]
    assert approaches_tried == 2, "Medium-confidence should not stop early; both approaches should be tried"
    assert call_count["n"] == 2


# ---------------------------------------------------------------------------
# Cumulative patch validation tests
# ---------------------------------------------------------------------------

async def test_accepted_patch_is_applied_permanently(monkeypatch, tmp_path):
    """After a patch is accepted, apply_diff should be called to make it permanent."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = _make_opportunity()
    patch = _make_patch()

    async def fake_discover(**kw):
        return [opp]

    async def fake_patchgen(**kw):
        return _make_outcome(patch)

    apply_calls: list[tuple] = []
    original_apply = None

    def tracking_apply(repo_dir, diff):
        apply_calls.append((repo_dir, diff))

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover)
    monkeypatch.setattr("runner.agent.orchestrator.generate_agent_patch_with_diagnostics", fake_patchgen)
    monkeypatch.setattr(
        "runner.agent.orchestrator.run_candidate_validation",
        lambda **kw: _make_simple_candidate(CONFIDENCE_MEDIUM),
    )
    monkeypatch.setattr("runner.agent.orchestrator.apply_diff", tracking_apply)

    emitted: list[tuple[str, str, dict]] = []
    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=5,
        on_event=lambda et, ph, data: emitted.append((et, ph, data)),
    )

    assert result.accepted_count == 1
    assert len(apply_calls) == 1, "apply_diff should be called once for the accepted patch"
    assert apply_calls[0][1] == patch.diff

    cumulative_events = [e for e in emitted if e[0] == "patch.applied_cumulative"]
    assert len(cumulative_events) == 1
    assert cumulative_events[0][2]["location"] == opp.location


async def test_rejected_patch_is_not_applied(monkeypatch, tmp_path):
    """When all variants are rejected, apply_diff should NOT be called."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = _make_opportunity()
    patch = _make_patch()

    async def fake_discover(**kw):
        return [opp]

    async def fake_patchgen(**kw):
        return _make_outcome(patch)

    apply_calls: list[tuple] = []

    def tracking_apply(repo_dir, diff):
        apply_calls.append((repo_dir, diff))

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover)
    monkeypatch.setattr("runner.agent.orchestrator.generate_agent_patch_with_diagnostics", fake_patchgen)
    monkeypatch.setattr(
        "runner.agent.orchestrator.run_candidate_validation",
        lambda **kw: _make_simple_candidate(CONFIDENCE_MEDIUM, accepted=False),
    )
    monkeypatch.setattr("runner.agent.orchestrator.apply_diff", tracking_apply)

    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=5,
    )

    assert result.accepted_count == 0
    assert len(apply_calls) == 0, "apply_diff should not be called for rejected patches"


async def test_apply_failure_downgrades_to_rejected(monkeypatch, tmp_path):
    """When apply_diff raises PatchApplyError, the candidate should be downgraded."""
    from runner.validator.patch_applicator import PatchApplyError

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp = _make_opportunity()
    patch = _make_patch()

    async def fake_discover(**kw):
        return [opp]

    async def fake_patchgen(**kw):
        return _make_outcome(patch)

    def failing_apply(repo_dir, diff):
        raise PatchApplyError("hunk FAILED -- saving rejects")

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover)
    monkeypatch.setattr("runner.agent.orchestrator.generate_agent_patch_with_diagnostics", fake_patchgen)
    monkeypatch.setattr(
        "runner.agent.orchestrator.run_candidate_validation",
        lambda **kw: _make_simple_candidate(CONFIDENCE_MEDIUM),
    )
    monkeypatch.setattr("runner.agent.orchestrator.apply_diff", failing_apply)

    emitted: list[tuple[str, str, dict]] = []
    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=5,
        on_event=lambda et, ph, data: emitted.append((et, ph, data)),
    )

    assert result.accepted_count == 0, "Candidate should be downgraded to rejected"
    assert result.candidate_results[0].is_accepted is False
    assert result.candidate_results[0].final_verdict.is_accepted is False
    assert "stacked" in result.candidate_results[0].final_verdict.reason.lower()

    fail_events = [e for e in emitted if e[0] == "patch.apply_failed"]
    assert len(fail_events) == 1
    assert "hunk FAILED" in fail_events[0][2]["error"]


async def test_second_patch_sees_repo_with_first_patch_applied(monkeypatch, tmp_path):
    """With 2 opportunities, the second patch gen call should operate on a repo
    that already has the first accepted patch applied."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ui.tsx").write_text("const x = 1;\n")

    opp1 = AgentOpportunity(
        type="performance",
        location="src/ui.tsx:1",
        rationale="reason 1",
        risk_level="low",
        approaches=["approach 1"],
        affected_lines=2,
        thinking_trace=_make_trace(),
    )
    opp2 = AgentOpportunity(
        type="performance",
        location="src/ui.tsx:2",
        rationale="reason 2",
        risk_level="low",
        approaches=["approach 2"],
        affected_lines=2,
        thinking_trace=_make_trace(),
    )

    patch1 = _make_patch()
    patch2 = AgentPatch(
        diff="--- a/src/ui.tsx\n+++ b/src/ui.tsx\n@@ -1 +1 @@\n-a\n+b\n",
        explanation="Second patch",
        touched_files=["src/ui.tsx"],
        estimated_lines_changed=2,
        thinking_trace=_make_trace("patch trace 2"),
    )

    # Track which patches apply_diff is called with (in order)
    applied_diffs: list[str] = []
    patchgen_call_count = {"n": 0}

    async def fake_discover(**kw):
        return [opp1, opp2]

    async def fake_patchgen(**kw):
        patchgen_call_count["n"] += 1
        if patchgen_call_count["n"] == 1:
            return _make_outcome(patch1)
        return _make_outcome(patch2)

    def tracking_apply(repo_dir, diff):
        applied_diffs.append(diff)

    monkeypatch.setattr("runner.agent.orchestrator.validate_model", lambda *a, **k: None)
    monkeypatch.setattr("runner.agent.orchestrator.get_provider", lambda *a, **k: MagicMock())
    monkeypatch.setattr("runner.agent.orchestrator.discover_opportunities", fake_discover)
    monkeypatch.setattr("runner.agent.orchestrator.generate_agent_patch_with_diagnostics", fake_patchgen)
    monkeypatch.setattr(
        "runner.agent.orchestrator.run_candidate_validation",
        lambda **kw: _make_simple_candidate(CONFIDENCE_MEDIUM),
    )
    monkeypatch.setattr("runner.agent.orchestrator.apply_diff", tracking_apply)

    result = await run_agent_cycle(
        repo_dir=tmp_path,
        detection=DetectionResult(test_cmd="npm test"),
        llm_config=_make_llm_config(),
        baseline=BaselineResult(is_success=True),
        max_candidates=5,
    )

    assert result.accepted_count == 2
    assert patchgen_call_count["n"] == 2
    assert len(applied_diffs) == 2, "Both accepted patches should be applied cumulatively"
    assert applied_diffs[0] == patch1.diff
    assert applied_diffs[1] == patch2.diff
