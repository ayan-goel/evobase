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
