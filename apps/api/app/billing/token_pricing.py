"""LLM token pricing registry.

Rates are stored as floats representing microdollars per token.
$X per 1 million tokens → X µ$/token.

Sources verified March 2026:
  Anthropic: https://platform.claude.com/docs/en/about-claude/pricing
  OpenAI:    https://platform.openai.com/docs/pricing
  Google:    https://ai.google.dev/gemini-api/docs/pricing

All monetary values are in microdollars (µ$). 1 µ$ = $0.000001.
Costs are rounded to the nearest integer µ$ when stored in bigint DB columns —
acceptable precision given token volumes per run.
"""

# microdollars per token  ($X per 1M tokens = X µ$/token)
TOKEN_RATES: dict[str, dict[str, dict[str, float]]] = {
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

WITHIN_PLAN_MARKUP = 1.5
OVERAGE_MARKUP = 2.0

# Fallback for unknown/future models — set conservatively high to avoid undercharging.
FALLBACK_RATE: dict[str, float] = {"input": 5.00, "output": 25.00}

# Included API budgets per tier in microdollars (the raw provider cost the platform absorbs).
# Users see dollar-equivalent values at 1.5× markup — e.g., Free = $5 visible, $3.33 API cost.
TIER_API_BUDGETS: dict[str, int] = {
    "free":    3_333_333,    # $3.33 API cost → $5.00 at 1.5×
    "hobby":   13_333_333,   # $13.33 API cost → $20.00 at 1.5×
    "premium": 40_000_000,   # $40.00 API cost → $60.00 at 1.5×
    "pro":     133_333_333,  # $133.33 API cost → $200.00 at 1.5×
}

TIER_OVERAGE_ALLOWED: dict[str, bool] = {
    "free":    False,
    "hobby":   True,
    "premium": True,
    "pro":     True,
}


def get_api_cost_microdollars(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> int:
    """Return raw API cost in microdollars (no markup applied)."""
    rates = TOKEN_RATES.get(provider, {}).get(model, FALLBACK_RATE)
    cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
    return round(cost)


def get_billed_microdollars(api_cost: int, within_plan: bool) -> int:
    """Apply the appropriate markup and return the amount to charge the user."""
    markup = WITHIN_PLAN_MARKUP if within_plan else OVERAGE_MARKUP
    return round(api_cost * markup)
