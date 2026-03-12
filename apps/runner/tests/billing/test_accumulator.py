"""Unit tests for UsageAccumulator.

Covers:
  - Normal recording (within plan)
  - Recording that crosses the budget boundary (rate_type switches to 'overage')
  - BudgetExceeded raised for free-tier orgs when budget is exhausted
  - BudgetExceeded raised when monthly spend limit is hit (paid tier)
  - Paid-tier overage allowed without raising
  - total_api_cost_microdollars / total_billed_microdollars properties
  - already_spent_microdollars counted toward budget
  - Multiple events accumulate correctly
"""

import pytest

from runner.billing.accumulator import BudgetExceeded, UsageAccumulator, UsageEvent
from runner.llm.types import ThinkingTrace


def _make_trace(
    provider: str = "anthropic",
    model: str = "claude-haiku-4-5",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> ThinkingTrace:
    return ThinkingTrace(
        model=model,
        provider=provider,
        reasoning="test",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _free_accumulator(budget: int = 3_333_333, already_spent: int = 0) -> UsageAccumulator:
    return UsageAccumulator(
        org_api_budget_microdollars=budget,
        overage_allowed=False,
        monthly_spend_limit_microdollars=None,
        already_spent_microdollars=already_spent,
    )


def _paid_accumulator(
    budget: int = 13_333_333,
    already_spent: int = 0,
    spend_limit: int | None = None,
) -> UsageAccumulator:
    return UsageAccumulator(
        org_api_budget_microdollars=budget,
        overage_allowed=True,
        monthly_spend_limit_microdollars=spend_limit,
        already_spent_microdollars=already_spent,
    )


class TestNormalRecording:
    def test_single_call_appends_event(self):
        acc = _free_accumulator()
        trace = _make_trace(prompt_tokens=10, completion_tokens=5)
        acc.record(trace, "file_selection")

        assert len(acc.events) == 1
        event = acc.events[0]
        assert event.call_type == "file_selection"
        assert event.provider == "anthropic"
        assert event.model == "claude-haiku-4-5"
        assert event.input_tokens == 10
        assert event.output_tokens == 5
        assert event.api_cost_microdollars > 0
        assert event.billed_microdollars > 0

    def test_within_plan_rate_type(self):
        acc = _free_accumulator(budget=10_000_000)
        acc.record(_make_trace(prompt_tokens=100, completion_tokens=50), "file_analysis")
        assert acc.events[0].rate_type == "included"

    def test_multiple_calls_accumulate(self):
        acc = _paid_accumulator()
        for call_type in ("file_selection", "file_analysis", "patch_gen", "self_correction"):
            acc.record(_make_trace(), call_type)

        assert len(acc.events) == 4
        assert acc.total_api_cost_microdollars == sum(e.api_cost_microdollars for e in acc.events)
        assert acc.total_billed_microdollars == sum(e.billed_microdollars for e in acc.events)

    def test_within_plan_markup_applied(self):
        acc = _free_accumulator(budget=10_000_000)
        acc.record(_make_trace(), "patch_gen")
        event = acc.events[0]
        # Billed should be 1.5× API cost (within plan)
        assert event.billed_microdollars == round(event.api_cost_microdollars * 1.5)

    def test_all_call_types_accepted(self):
        acc = _paid_accumulator()
        for call_type in ("file_selection", "file_analysis", "patch_gen", "self_correction"):
            acc.record(_make_trace(), call_type)
        assert len(acc.events) == 4


class TestBudgetEnforcement:
    def test_free_tier_raises_budget_exceeded_when_exhausted(self):
        # Set already_spent to almost full budget, then push it over
        acc = _free_accumulator(budget=1_000, already_spent=900)
        # A small call should push us over the 1000 µ$ budget
        # claude-haiku-4-5: $1.00/M input, $5.00/M output = 1+5=6 µ$/token at 100+50 = 175 µ$
        # With 900 already spent, 900+175 = 1075 > 1000 → BudgetExceeded
        with pytest.raises(BudgetExceeded) as exc_info:
            acc.record(_make_trace(prompt_tokens=100, completion_tokens=50), "patch_gen")
        assert exc_info.value.budget == 1_000
        assert exc_info.value.spent > 1_000

    def test_free_tier_event_still_recorded_before_raise(self):
        """The event causing the budget breach is appended before the exception is raised."""
        acc = _free_accumulator(budget=1_000, already_spent=900)
        with pytest.raises(BudgetExceeded):
            acc.record(_make_trace(prompt_tokens=100, completion_tokens=50), "patch_gen")
        # Event was appended
        assert len(acc.events) == 1

    def test_free_tier_does_not_raise_under_budget(self):
        acc = _free_accumulator(budget=10_000_000)  # Very large budget
        acc.record(_make_trace(prompt_tokens=100, completion_tokens=50), "file_selection")
        assert len(acc.events) == 1

    def test_paid_tier_does_not_raise_over_included_budget(self):
        """Paid tiers in overage should NOT raise — they continue at 2× rate."""
        acc = _paid_accumulator(budget=1_000, already_spent=900)
        # This call puts us over the included budget — but paid orgs can continue
        acc.record(_make_trace(prompt_tokens=100, completion_tokens=50), "patch_gen")
        assert len(acc.events) == 1

    def test_paid_tier_overage_rate_type(self):
        """Once over the included budget, rate_type should be 'overage'."""
        acc = _paid_accumulator(budget=1_000, already_spent=1_000)
        acc.record(_make_trace(), "patch_gen")
        assert acc.events[0].rate_type == "overage"

    def test_paid_tier_overage_markup_applied(self):
        """Overage events use 2.0× markup instead of 1.5×."""
        acc = _paid_accumulator(budget=1_000, already_spent=1_000)
        acc.record(_make_trace(), "patch_gen")
        event = acc.events[0]
        assert event.billed_microdollars == round(event.api_cost_microdollars * 2.0)

    def test_monthly_spend_limit_enforced_for_paid_tier(self):
        """Paid org with a spend limit raises BudgetExceeded when the cap is hit."""
        acc = _paid_accumulator(
            budget=13_333_333,
            already_spent=50_000,
            spend_limit=51_000,
        )
        with pytest.raises(BudgetExceeded):
            acc.record(_make_trace(prompt_tokens=1000, completion_tokens=1000), "patch_gen")

    def test_monthly_spend_limit_not_triggered_under_cap(self):
        """No exception when spend is safely under the cap."""
        acc = _paid_accumulator(
            budget=13_333_333,
            already_spent=0,
            spend_limit=10_000_000,
        )
        acc.record(_make_trace(), "patch_gen")
        assert len(acc.events) == 1

    def test_already_spent_counted_toward_budget(self):
        """already_spent_microdollars reduces remaining budget for the current run."""
        # Budget = 100, already_spent = 100 → any further call exceeds budget
        acc = _free_accumulator(budget=100, already_spent=100)
        with pytest.raises(BudgetExceeded):
            acc.record(_make_trace(prompt_tokens=10, completion_tokens=5), "file_selection")


class TestProperties:
    def test_total_api_cost_empty(self):
        assert _free_accumulator().total_api_cost_microdollars == 0

    def test_total_billed_empty(self):
        assert _free_accumulator().total_billed_microdollars == 0

    def test_total_api_cost_accumulates(self):
        acc = _paid_accumulator(budget=100_000_000)
        acc.record(_make_trace(prompt_tokens=1000, completion_tokens=500), "file_selection")
        acc.record(_make_trace(prompt_tokens=2000, completion_tokens=1000), "patch_gen")
        expected = sum(e.api_cost_microdollars for e in acc.events)
        assert acc.total_api_cost_microdollars == expected

    def test_total_billed_accumulates(self):
        acc = _paid_accumulator(budget=100_000_000)
        acc.record(_make_trace(), "file_analysis")
        acc.record(_make_trace(), "patch_gen")
        expected = sum(e.billed_microdollars for e in acc.events)
        assert acc.total_billed_microdollars == expected

    def test_openai_model_rates_correct(self):
        acc = _paid_accumulator(budget=100_000_000)
        trace = _make_trace(provider="openai", model="gpt-4.1", prompt_tokens=1000, completion_tokens=1000)
        acc.record(trace, "patch_gen")
        # $2.00/M input + $8.00/M output = 2000 + 8000 = 10000 µ$
        assert acc.events[0].api_cost_microdollars == 10000

    def test_google_model_rates_correct(self):
        acc = _paid_accumulator(budget=100_000_000)
        trace = _make_trace(provider="google", model="gemini-3-flash", prompt_tokens=2000, completion_tokens=1000)
        acc.record(trace, "file_selection")
        # $0.50/M input + $3.00/M output = 1000 + 3000 = 4000 µ$
        assert acc.events[0].api_cost_microdollars == 4000
