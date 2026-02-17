"""LLM configuration endpoints.

Routes:
  GET /llm/models  — list all available models grouped by provider

This is a static catalogue endpoint — no auth required for MVP since
the model list is public information. The runner reads API keys from
environment variables, not from this endpoint.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/llm", tags=["llm"])

# Static registry of supported models per provider.
# Kept here (not in the runner) so the frontend can populate
# the model selector without a runner dependency.
AVAILABLE_MODELS: dict[str, list[dict]] = {
    "openai": [
        {"id": "gpt-4o", "label": "GPT-4o", "description": "Best general-purpose model"},
        {"id": "gpt-4o-mini", "label": "GPT-4o Mini", "description": "Faster, lower cost"},
        {"id": "o3-mini", "label": "o3-mini", "description": "Reasoning model, highest quality"},
    ],
    "anthropic": [
        {
            "id": "claude-sonnet-4-5",
            "label": "Claude Sonnet 4.5",
            "description": "Best reasoning-to-cost ratio (recommended)",
        },
        {
            "id": "claude-haiku-3-5",
            "label": "Claude Haiku 3.5",
            "description": "Fastest, lowest cost",
        },
    ],
    "google": [
        {
            "id": "gemini-2.0-flash",
            "label": "Gemini 2.0 Flash",
            "description": "Fast and capable (recommended)",
        },
        {
            "id": "gemini-1.5-pro",
            "label": "Gemini 1.5 Pro",
            "description": "Long context, high quality",
        },
    ],
}


@router.get("/models")
async def list_models() -> dict:
    """Return all available LLM models grouped by provider.

    Used by the frontend settings panel to populate provider and model
    selector dropdowns.
    """
    return {
        "providers": [
            {
                "id": provider_id,
                "label": provider_id.capitalize(),
                "models": models,
            }
            for provider_id, models in AVAILABLE_MODELS.items()
        ]
    }
