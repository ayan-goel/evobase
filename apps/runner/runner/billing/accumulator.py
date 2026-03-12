"""Per-run token usage accumulator.

Tracks every provider.complete() call during a run, computes the API cost
(and billed amount with markup), enforces free-tier mid-run budget stopping,
and produces the list of UsageEvent records to be written to token_usage_events
at run completion.

Design:
- Constructed by runs/service.py at run start with the org's subscription data.
- Passed (optionally) into discovery and patchgen; callers call record() after
  every LLM call.
- On BudgetExceeded the run is terminated gracefully and the events collected
  so far are still written to the DB for auditability.
"""

import logging
from dataclasses import dataclass, field

from runner.llm.types import ThinkingTrace

logger = logging.getLogger(__name__)

# microdollars per token  ($X per 1M tokens = X µ$/token)
_TOKEN_RATES: dict[str, dict[str, dict[str, float]]] = {
    "anthropic": {
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-opus-4-6":   {"input": 5.00, "output": 25.00},
        "claude-haiku-4-5":  {"input": 1.00, "output":  5.00},
    },
    "openai": {
        "gpt-4.1":    {"input": 2.00, "output":  8.00},
        "gpt-5.3":    {"input": 1.75, "output": 14.00},
        "gpt-5-mini": {"input": 0.25, "output":  2.00},
    },
    "google": {
        "gemini-3-pro":        {"input": 2.00, "output": 12.00},
        "gemini-3-flash":      {"input": 0.50, "output":  3.00},
        "gemini-3-flash-lite": {"input": 0.25, "output":  1.50},
    },
}
_FALLBACK_RATE: dict[str, float] = {"input": 5.00, "output": 25.00}
_WITHIN_PLAN_MARKUP = 1.5
_OVERAGE_MARKUP = 2.0


@dataclass
class UsageEvent:
    """Single LLM call record to be written to token_usage_events."""
    call_type: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    api_cost_microdollars: int
    billed_microdollars: int
    rate_type: str  # "included" | "overage"


class BudgetExceeded(Exception):
    """Raised when a free-tier org exhausts its included API budget mid-run."""

    def __init__(self, spent: int, budget: int) -> None:
        self.spent = spent
        self.budget = budget
        super().__init__(
            f"Budget exhausted: spent {spent} µ$ of {budget} µ$ included budget"
        )


@dataclass
class UsageAccumulator:
    """Accumulates per-call LLM usage for a single run.

    Args:
        org_api_budget_microdollars: The org's included API budget for this period.
        overage_allowed: Whether the org can go into pay-as-you-go overage.
        monthly_spend_limit_microdollars: Optional user-configured spend cap (overage).
        already_spent_microdollars: Sum of api_cost_microdollars for all prior runs
            in the current billing period (pre-loaded from token_usage_events).
    """
    org_api_budget_microdollars: int
    overage_allowed: bool
    monthly_spend_limit_microdollars: int | None
    already_spent_microdollars: int
    events: list[UsageEvent] = field(default_factory=list)

    def record(self, trace: ThinkingTrace, call_type: str) -> None:
        """Compute cost for this LLM call, append an event, and enforce budget.

        For free-tier orgs (overage_allowed=False): raises BudgetExceeded when the
        accumulated API cost (already_spent + this run's cost) exceeds the budget.

        For paid orgs: records at the 'overage' rate_type once the budget is exceeded,
        subject to monthly_spend_limit_microdollars if set.

        Args:
            trace: ThinkingTrace from the LLM response (carries token counts).
            call_type: One of 'file_selection', 'file_analysis', 'patch_gen', 'self_correction'.

        Raises:
            BudgetExceeded: Free-tier org has exhausted the included budget.
        """
        api_cost = _compute_api_cost(trace.provider, trace.model, trace.prompt_tokens, trace.completion_tokens)

        # Determine whether this call is within the plan or in overage
        total_spent_before = self.already_spent_microdollars + self.total_api_cost_microdollars
        within_plan = total_spent_before < self.org_api_budget_microdollars
        rate_type = "included" if within_plan else "overage"
        billed = round(api_cost * (_WITHIN_PLAN_MARKUP if within_plan else _OVERAGE_MARKUP))

        event = UsageEvent(
            call_type=call_type,
            provider=trace.provider,
            model=trace.model,
            input_tokens=trace.prompt_tokens,
            output_tokens=trace.completion_tokens,
            api_cost_microdollars=api_cost,
            billed_microdollars=billed,
            rate_type=rate_type,
        )
        self.events.append(event)

        new_total = total_spent_before + api_cost

        logger.debug(
            "UsageAccumulator.record: call_type=%s model=%s tokens=%d+%d "
            "api_cost=%dµ$ billed=%dµ$ rate=%s total_period=%dµ$ budget=%dµ$",
            call_type, trace.model, trace.prompt_tokens, trace.completion_tokens,
            api_cost, billed, rate_type, new_total, self.org_api_budget_microdollars,
        )

        # Free tier: stop mid-run when budget is exhausted
        if not self.overage_allowed and new_total > self.org_api_budget_microdollars:
            logger.warning(
                "Free-tier budget exhausted: period_spent=%dµ$ budget=%dµ$ — stopping run",
                new_total, self.org_api_budget_microdollars,
            )
            raise BudgetExceeded(new_total, self.org_api_budget_microdollars)

        # Paid tier: enforce optional monthly spend cap
        if (
            self.overage_allowed
            and self.monthly_spend_limit_microdollars is not None
            and new_total > self.monthly_spend_limit_microdollars
        ):
            logger.warning(
                "Monthly spend limit reached: period_spent=%dµ$ limit=%dµ$ — stopping run",
                new_total, self.monthly_spend_limit_microdollars,
            )
            raise BudgetExceeded(new_total, self.monthly_spend_limit_microdollars)

    @property
    def total_api_cost_microdollars(self) -> int:
        """Sum of raw API costs for all calls recorded in this run."""
        return sum(e.api_cost_microdollars for e in self.events)

    @property
    def total_billed_microdollars(self) -> int:
        """Sum of billed amounts (after markup) for all calls in this run."""
        return sum(e.billed_microdollars for e in self.events)


def _compute_api_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> int:
    """Return raw API cost in microdollars for one LLM call."""
    rates = _TOKEN_RATES.get(provider, {}).get(model, _FALLBACK_RATE)
    return round((input_tokens * rates["input"]) + (output_tokens * rates["output"]))
