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
    """

    provider: str  # "openai" | "anthropic" | "google"
    model: str     # e.g. "claude-sonnet-4-5", "gpt-4o", "gemini-2.0-flash"
    api_key: str
    max_tokens: int = 4096
    temperature: float = 0.2
    enable_thinking: bool = True  # Use extended thinking / CoT when available


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
    "openai": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
    "anthropic": ["claude-sonnet-4-5", "claude-haiku-3-5"],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro"],
}

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL = "claude-sonnet-4-5"
