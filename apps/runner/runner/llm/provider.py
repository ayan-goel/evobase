"""Abstract LLMProvider protocol.

All provider implementations must conform to this interface.
The protocol approach (structural subtyping) avoids the need for
an abstract base class while still being statically checkable.
"""

from typing import Optional, Protocol, runtime_checkable

from runner.llm.types import LLMConfig, LLMMessage, LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM provider implementations.

    Each provider handles its own auth, retry, and error mapping.
    Callers interact only with this interface.
    """

    async def complete(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Send messages to the LLM and return a structured response.

        Args:
            messages: Ordered conversation history (system, then user turns).
            config: Provider-specific configuration including API key.

        Returns:
            LLMResponse with content string and captured thinking trace.

        Raises:
            LLMProviderError: On API failure, auth error, or rate limit.
        """
        ...  # noqa: PLR6301


class LLMProviderError(Exception):
    """Raised by provider implementations on non-retryable failures.

    Carries the provider name and original error for upstream logging.
    """

    def __init__(self, provider: str, message: str, cause: Optional[Exception] = None):
        self.provider = provider
        self.cause = cause
        super().__init__(f"[{provider}] {message}")


