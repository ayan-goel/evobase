"""Framework-specific focus strings for the LLM system prompt.

Each sub-module exports a single ``FOCUS`` constant (a multi-line string) that
combines the original bullet-point focus areas with a structured rule catalog
derived from framework-specific optimisation research.

Public API
----------
get_framework_focus(framework) -> str
    Return the focus block for the given framework identifier string.
    Falls back to the generic JS/TS focus when the framework is unknown.
"""

from .angular import FOCUS as _ANGULAR
from .express import FOCUS as _EXPRESS
from .fastapi import FOCUS as _FASTAPI
from .fastify import FOCUS as _FASTIFY
from .flask import FOCUS as _FLASK
from .django import FOCUS as _DJANGO
from .go import FOCUS as _GO
from .jvm import FOCUS as _JVM
from .nestjs import FOCUS as _NESTJS
from .nextjs import FOCUS as _NEXTJS
from .node import FOCUS as _NODE
from .python import FOCUS as _PYTHON
from .rails import FOCUS as _RAILS
from .react_vite import FOCUS as _REACT_VITE
from .rust import FOCUS as _RUST
from .springboot import FOCUS as _SPRINGBOOT
from .svelte import FOCUS as _SVELTE
from .vue import FOCUS as _VUE

# Generic JS/TS focus (fallback for unrecognised JS/TS frameworks)
_GENERIC_JS_FOCUS = """
General JavaScript / TypeScript focus areas:
- Array membership tests using `indexOf(x) !== -1` instead of `includes(x)`.
- Regex objects constructed inside loops that could be hoisted to module scope.
- Repeated `JSON.parse` / `JSON.stringify` on the same value within a function.
- String concatenation in loops using `+=` instead of building an array and
  joining.
- Synchronous filesystem operations in hot paths.
- Dead code: unreachable statements after `return` or `throw`.
- Redundant object spreads in reduce accumulators creating excessive allocations.
"""


def get_framework_focus(framework: str | None) -> str:
    """Return the framework-specific focus block for the given framework name.

    The *framework* string comes from the detector's ``DetectionResult.framework``
    field and is matched case-insensitively using substring/equality rules that
    mirror the original ``_get_framework_focus`` logic.

    Parameters
    ----------
    framework:
        Framework identifier from the detector, or ``None`` for generic JS/TS.

    Returns
    -------
    str
        Multi-line focus string for the framework.
    """
    if not framework:
        return _GENERIC_JS_FOCUS

    fw = framework.lower()

    # Python frameworks
    if fw == "fastapi":
        return _FASTAPI
    if fw == "django":
        return _DJANGO
    if fw == "flask":
        return _FLASK
    if fw in ("starlette", "aiohttp", "tornado", "litestar"):
        return _PYTHON

    # Go frameworks
    if fw in ("go", "gin", "echo", "fiber", "chi", "gorilla"):
        return _GO

    # Rust frameworks
    if fw in ("rust", "axum", "actix", "rocket", "warp", "poem", "salvo", "tide"):
        return _RUST

    # Ruby frameworks
    if fw in ("ruby", "rails", "grape", "sinatra", "hanami", "roda", "padrino"):
        return _RAILS

    # JVM frameworks
    if fw in ("spring-boot", "spring-webflux", "spring-mvc"):
        return _SPRINGBOOT
    if fw in ("java", "quarkus", "micronaut", "kotlin"):
        return _JVM

    # JavaScript / TypeScript frameworks — order matters: more specific first
    if "next" in fw:
        return _NEXTJS
    if "nest" in fw:
        return _NESTJS
    if "nuxt" in fw:
        return _VUE
    if "vue" in fw:
        return _VUE
    if "svelte" in fw:
        return _SVELTE
    if "angular" in fw:
        return _ANGULAR
    if "fastify" in fw:
        return _FASTIFY
    if "express" in fw:
        return _EXPRESS
    if "gatsby" in fw or "remix" in fw:
        return _REACT_VITE
    if "react" in fw or "vite" in fw:
        return _REACT_VITE
    if "koa" in fw or "hapi" in fw:
        return _NODE

    return _GENERIC_JS_FOCUS


__all__ = ["get_framework_focus"]
