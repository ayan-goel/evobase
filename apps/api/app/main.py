from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.repos.router import router as repos_router
from app.runs.router import router as runs_router
from app.proposals.router import router as proposals_router
from app.artifacts.router import router as artifacts_router
from app.github.router import router as github_router
from app.settings.router import router as settings_router
from app.llm.router import router as llm_router

# Import scheduler so Celery beat_schedule is registered when the app starts
import app.scheduling.scheduler  # noqa: F401


def create_app() -> FastAPI:
    settings = get_settings()

    _app = FastAPI(
        title="SelfOpt API",
        description="Control Plane API for SelfOpt autonomous code optimization",
        version="0.1.0",
    )

    # ---------------------------------------------------------------------------
    # Rate limiter state — SlowAPI reads limiter from app.state
    # ---------------------------------------------------------------------------
    _app.state.limiter = limiter
    _app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ---------------------------------------------------------------------------
    # Middleware (registered outermost → innermost; executed innermost → outermost)
    # ---------------------------------------------------------------------------

    # CORS — must be added before other custom middleware so preflight OPTIONS
    # requests are handled before they reach downstream middleware.
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # SlowAPI — must be before security headers so 429s also get security headers
    _app.add_middleware(SlowAPIMiddleware)

    # Security headers on every response
    _app.add_middleware(SecurityHeadersMiddleware)

    # Request ID — inject / forward X-Request-ID and bind to ContextVar
    _app.add_middleware(RequestIdMiddleware)

    # ---------------------------------------------------------------------------
    # Sentry — initialised here so it captures startup errors too
    # ---------------------------------------------------------------------------
    from app.core.sentry import init_sentry

    init_sentry(
        dsn=settings.sentry_dsn,
        environment="development" if settings.debug else "production",
    )

    # ---------------------------------------------------------------------------
    # Logging — configure structlog before any routers log anything
    # ---------------------------------------------------------------------------
    from app.core.logging import configure_structlog

    configure_structlog(debug=settings.debug)

    # ---------------------------------------------------------------------------
    # Routes
    # ---------------------------------------------------------------------------

    @_app.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    _app.include_router(repos_router)
    _app.include_router(runs_router)
    _app.include_router(proposals_router)
    _app.include_router(artifacts_router)
    _app.include_router(github_router)
    _app.include_router(settings_router)
    _app.include_router(llm_router)

    return _app


app = create_app()
