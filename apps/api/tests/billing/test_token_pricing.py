"""Unit tests for the token pricing registry.

Covers:
  - Known model rates return correct microdollar costs
  - Unknown model falls back to the conservative fallback rate
  - Markup logic: 1.5× within plan, 2.0× overage
  - Zero-token edge cases
  - Mixed provider/model keys don't cross-contaminate
"""

import pytest

from app.billing.token_pricing import (
    FALLBACK_RATE,
    TIER_API_BUDGETS,
    TIER_OVERAGE_ALLOWED,
    TOKEN_RATES,
    get_api_cost_microdollars,
    get_billed_microdollars,
)


class TestGetApiCostMicrodollars:
    def test_claude_sonnet_known_model(self):
        # $3.00/M input, $15.00/M output
        # 1000 input → 3000 µ$;  500 output → 7500 µ$  → 10500 µ$
        cost = get_api_cost_microdollars("anthropic", "claude-sonnet-4-6", 1000, 500)
        assert cost == 10500

    def test_claude_haiku_low_cost(self):
        # $1.00/M input, $5.00/M output
        # 2000 input → 2000 µ$; 1000 output → 5000 µ$ → 7000 µ$
        cost = get_api_cost_microdollars("anthropic", "claude-haiku-4-5", 2000, 1000)
        assert cost == 7000

    def test_gpt_4_1(self):
        # $2.00/M input, $8.00/M output
        # 500 input → 1000 µ$; 250 output → 2000 µ$ → 3000 µ$
        cost = get_api_cost_microdollars("openai", "gpt-4.1", 500, 250)
        assert cost == 3000

    def test_gpt_5_3(self):
        # $1.75/M input, $14.00/M output
        # 1000 input → 1750 µ$; 1000 output → 14000 µ$ → 15750 µ$
        cost = get_api_cost_microdollars("openai", "gpt-5.3", 1000, 1000)
        assert cost == 15750

    def test_gpt_5_mini(self):
        # $0.25/M input, $2.00/M output
        # 4000 input → 1000 µ$; 2000 output → 4000 µ$ → 5000 µ$
        cost = get_api_cost_microdollars("openai", "gpt-5-mini", 4000, 2000)
        assert cost == 5000

    def test_gemini_3_pro(self):
        # $2.00/M input, $12.00/M output
        cost = get_api_cost_microdollars("google", "gemini-3-pro", 1000, 1000)
        assert cost == 14000

    def test_gemini_3_flash(self):
        # $0.50/M input, $3.00/M output
        cost = get_api_cost_microdollars("google", "gemini-3-flash", 2000, 1000)
        assert cost == 4000

    def test_gemini_3_flash_lite(self):
        # $0.25/M input, $1.50/M output
        cost = get_api_cost_microdollars("google", "gemini-3-flash-lite", 4000, 2000)
        assert cost == 4000

    def test_unknown_model_uses_fallback(self):
        # Fallback is $5.00/M input, $25.00/M output — conservatively high
        cost = get_api_cost_microdollars("openai", "gpt-99-future", 1000, 1000)
        fallback_cost = round((1000 * FALLBACK_RATE["input"]) + (1000 * FALLBACK_RATE["output"]))
        assert cost == fallback_cost

    def test_unknown_provider_uses_fallback(self):
        cost = get_api_cost_microdollars("future_provider", "some-model", 1000, 0)
        assert cost == round(1000 * FALLBACK_RATE["input"])

    def test_zero_tokens_returns_zero(self):
        cost = get_api_cost_microdollars("anthropic", "claude-sonnet-4-6", 0, 0)
        assert cost == 0

    def test_zero_input_tokens(self):
        # Only output tokens
        cost = get_api_cost_microdollars("anthropic", "claude-sonnet-4-6", 0, 1000)
        assert cost == round(1000 * TOKEN_RATES["anthropic"]["claude-sonnet-4-6"]["output"])

    def test_zero_output_tokens(self):
        # Only input tokens
        cost = get_api_cost_microdollars("anthropic", "claude-haiku-4-5", 1000, 0)
        assert cost == round(1000 * TOKEN_RATES["anthropic"]["claude-haiku-4-5"]["input"])

    def test_all_nine_models_defined(self):
        """Ensure every model in the rate table returns a non-zero cost for non-zero tokens."""
        for provider, models in TOKEN_RATES.items():
            for model in models:
                cost = get_api_cost_microdollars(provider, model, 1000, 1000)
                assert cost > 0, f"{provider}/{model} returned zero cost"

    def test_rounding_is_deterministic(self):
        """Same inputs always produce the same output."""
        cost1 = get_api_cost_microdollars("openai", "gpt-5.3", 777, 333)
        cost2 = get_api_cost_microdollars("openai", "gpt-5.3", 777, 333)
        assert cost1 == cost2


class TestGetBilledMicrodollars:
    def test_within_plan_markup_is_1_5x(self):
        billed = get_billed_microdollars(10000, within_plan=True)
        assert billed == 15000

    def test_overage_markup_is_2x(self):
        billed = get_billed_microdollars(10000, within_plan=False)
        assert billed == 20000

    def test_zero_api_cost_yields_zero_billed(self):
        assert get_billed_microdollars(0, within_plan=True) == 0
        assert get_billed_microdollars(0, within_plan=False) == 0

    def test_billed_always_greater_than_api_cost(self):
        api_cost = 5000
        assert get_billed_microdollars(api_cost, within_plan=True) > api_cost
        assert get_billed_microdollars(api_cost, within_plan=False) > api_cost

    def test_overage_billed_exceeds_within_plan(self):
        api_cost = 8000
        assert get_billed_microdollars(api_cost, within_plan=False) > get_billed_microdollars(api_cost, within_plan=True)


class TestTierBudgets:
    def test_free_tier_budget(self):
        # $3.33 API cost → 3333333 µ$  (rounds down)
        assert TIER_API_BUDGETS["free"] == 3_333_333

    def test_hobby_tier_budget(self):
        # $13.33 API cost → 13333333 µ$
        assert TIER_API_BUDGETS["hobby"] == 13_333_333

    def test_premium_tier_budget(self):
        assert TIER_API_BUDGETS["premium"] == 40_000_000

    def test_pro_tier_budget(self):
        assert TIER_API_BUDGETS["pro"] == 133_333_333

    def test_paid_tiers_allow_overage(self):
        for tier in ("hobby", "premium", "pro"):
            assert TIER_OVERAGE_ALLOWED[tier] is True

    def test_free_tier_blocks_overage(self):
        assert TIER_OVERAGE_ALLOWED["free"] is False

    def test_budgets_increase_with_tier(self):
        budgets = [TIER_API_BUDGETS[t] for t in ("free", "hobby", "premium", "pro")]
        assert budgets == sorted(budgets), "Budgets should increase from free → pro"
