"""Parametrized tests for the frameworks/ focus dispatch table.

Verifies that every supported framework identifier resolves to a non-empty
focus string and that the returned string contains at least a basic marker
proving the correct module was returned (not the generic fallback by mistake).
"""

import pytest

from runner.llm.prompts.frameworks import get_framework_focus


# ---------------------------------------------------------------------------
# Each tuple: (framework_id, expected_substring)
# The expected_substring is a short token that should appear in the correct
# module's FOCUS but NOT in the generic fallback.
# ---------------------------------------------------------------------------
_FRAMEWORK_CASES: list[tuple[str, str]] = [
    # Next.js
    ("nextjs", "use client"),
    ("next", "use client"),
    # NestJS
    ("nestjs", "NestJS"),
    ("nest", "NestJS"),
    # Express
    ("express", "Express"),
    # React / Vite
    ("react", "React.memo"),
    ("vite", "React.memo"),
    ("gatsby", "React.memo"),
    ("remix", "React.memo"),
    ("react-vite", "React.memo"),
    # Vue / Nuxt
    ("vue", "v-for"),
    ("nuxt", "v-for"),
    # Angular
    ("angular", "OnPush"),
    # Svelte / SvelteKit
    ("svelte", "onDestroy"),
    ("sveltekit", "onDestroy"),
    # Fastify
    ("fastify", "Fastify"),
    # Generic Node (koa, hapi)
    ("koa", "Node.js"),
    ("hapi", "Node.js"),
    # FastAPI
    ("fastapi", "FastAPI"),
    # Django
    ("django", "Django"),
    # Flask
    ("flask", "Flask"),
    # Generic Python (starlette, aiohttp, tornado, litestar)
    ("starlette", "async def"),
    ("aiohttp", "async def"),
    ("tornado", "async def"),
    ("litestar", "async def"),
    # Go
    ("go", "goroutine"),
    ("gin", "goroutine"),
    ("echo", "goroutine"),
    ("fiber", "goroutine"),
    ("chi", "goroutine"),
    ("gorilla", "goroutine"),
    # Rust
    ("rust", "clone"),
    ("axum", "clone"),
    ("actix", "clone"),
    ("rocket", "clone"),
    ("warp", "clone"),
    # Rails / Ruby
    ("rails", "Active Record"),
    ("ruby", "Active Record"),
    ("grape", "Active Record"),
    ("sinatra", "Active Record"),
    ("hanami", "Active Record"),
    ("roda", "Active Record"),
    ("padrino", "Active Record"),
    # Spring Boot
    ("spring-boot", "Transactional"),
    ("spring-webflux", "Transactional"),
    ("spring-mvc", "Transactional"),
    # Generic JVM
    ("java", "Optional"),
    ("quarkus", "Optional"),
    ("micronaut", "Optional"),
    ("kotlin", "Optional"),
]


@pytest.mark.parametrize("framework,expected", _FRAMEWORK_CASES, ids=[f[0] for f in _FRAMEWORK_CASES])
def test_get_framework_focus_returns_non_empty(framework: str, expected: str) -> None:
    """get_framework_focus(fw) returns a non-empty string containing a known marker."""
    focus = get_framework_focus(framework)
    assert focus, f"get_framework_focus({framework!r}) returned an empty string"
    assert expected in focus, (
        f"get_framework_focus({framework!r}) did not contain expected marker {expected!r}.\n"
        f"Returned focus (first 300 chars):\n{focus[:300]}"
    )


def test_get_framework_focus_none_returns_generic() -> None:
    """None framework falls back to the generic JS/TS focus."""
    focus = get_framework_focus(None)
    assert focus
    # Generic JS/TS focus should mention indexOf or includes
    assert "indexOf" in focus or "includes" in focus


def test_get_framework_focus_unknown_returns_generic() -> None:
    """Unrecognised framework falls back to the generic JS/TS focus."""
    focus = get_framework_focus("some-unknown-framework-xyz")
    assert focus
    assert "JavaScript" in focus or "TypeScript" in focus


def test_all_focus_strings_contain_rule_catalog() -> None:
    """Every named framework's FOCUS string contains the structured rule catalog block."""
    named_frameworks = [fw for fw, _ in _FRAMEWORK_CASES]
    for fw in set(named_frameworks):
        focus = get_framework_focus(fw)
        assert "Rule " in focus or "Anti-pattern" in focus, (
            f"Framework {fw!r} focus string appears to be missing the rule catalog block.\n"
            f"First 200 chars: {focus[:200]}"
        )
