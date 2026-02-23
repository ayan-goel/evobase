"""Shared types for the LLM provider layer.

All provider implementations produce `LLMResponse` and capture
`ThinkingTrace` objects so reasoning is persisted alongside results.

Design principles:
- Provider-agnostic: callers only see `LLMMessage`, `LLMConfig`, `LLMResponse`.
- Reasoning is first-class: every response carries the model's thinking trace.
- Serializable: all types have `to_dict()` for DB storage (JSON columns).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class LLMConfig:
    """Per-call LLM configuration.

    api_key is read from environment at call time; never stored in DB.
    max_tokens caps completion length; defaults are provider-appropriate.
    temperature=0 ensures deterministic outputs for patch generation.

    thinking_budget_tokens: Anthropic-only — max tokens for the extended
        thinking block.  Use 0 to disable thinking entirely.
    reasoning_effort: OpenAI reasoning-model-only — "low" | "medium" | "high".
    """

    provider: str  # "openai" | "anthropic" | "google"
    model: str     # e.g. "claude-sonnet-4-6", "gpt-5.2", "gemini-2.5-pro"
    api_key: str
    max_tokens: int = 4096
    temperature: float = 0.2
    enable_thinking: bool = True   # Use extended thinking when supported
    thinking_budget_tokens: int = 4000   # Anthropic: per-call thinking budget
    reasoning_effort: str = "high"       # OpenAI reasoning models: effort tier


@dataclass
class LLMMessage:
    """A single message in the conversation."""

    role: str     # "system" | "user" | "assistant"
    content: str


@dataclass
class ThinkingTrace:
    """Captured reasoning from the model's internal chain-of-thought.

    For Anthropic: extracted from `thinking` content blocks.
    For OpenAI: extracted from the `reasoning` field in structured JSON output.
    For Google: extracted from the `reasoning` field in structured JSON output.

    Stored in DB as JSON so it can be displayed in the UI reasoning viewer.
    """

    model: str
    provider: str
    reasoning: str          # Full reasoning / thinking text
    prompt_tokens: int
    completion_tokens: int
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "reasoning": self.reasoning,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "tokens_used": self.prompt_tokens + self.completion_tokens,
            "timestamp": self.timestamp,
        }


@dataclass
class LLMResponse:
    """Structured response from any provider.

    `content` is the actual JSON payload returned by the model.
    `thinking_trace` carries the captured reasoning.
    """

    content: str                           # Raw text / JSON string from model
    thinking_trace: ThinkingTrace
    finish_reason: str = "stop"            # "stop" | "length" | "error"

    def is_complete(self) -> bool:
        """Return True if the response completed normally."""
        return self.finish_reason == "stop"


# ---------------------------------------------------------------------------
# Available models registry (used by the /llm/models API endpoint)
# ---------------------------------------------------------------------------

AVAILABLE_MODELS: dict[str, list[str]] = {
    "anthropic": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
    "openai": ["gpt-5.2", "gpt-5-mini"],
    "google": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
}

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Cheap model to use for the file-selection stage only
# ---------------------------------------------------------------------------

_SELECTION_MODEL: dict[str, str] = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-5-mini",
    "google": "gemini-2.5-flash",
}


def get_selection_model(provider: str, current_model: str) -> str:
    """Return the cheap model to use for the file-selection stage.

    Falls back to the current model if the provider is not in the map
    (e.g. a future provider) so callers never receive an empty string.
    """
    return _SELECTION_MODEL.get(provider, current_model)
