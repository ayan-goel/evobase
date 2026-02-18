from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalise_db_url(url: str) -> str:
    """Ensure the DATABASE_URL uses the asyncpg driver prefix.

    Supabase cloud (and Railway's Postgres plugin) emit plain
    ``postgresql://`` connection strings.  SQLAlchemy's async engine
    requires ``postgresql+asyncpg://``.  This validator adds the suffix
    when it is absent so both formats are accepted transparently.
    """
    if url.startswith("postgresql://") or url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1).replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )
    return url


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Supabase credentials are required for DB and storage access.
    DATABASE_URL points to the Supabase Postgres instance directly.

    Accepted DATABASE_URL formats
    ─────────────────────────────
    • postgresql+asyncpg://...   (explicit driver — recommended)
    • postgresql://...           (Supabase cloud / Railway plugin default)
    • postgres://...             (legacy Heroku-style alias)

    All three are normalised to ``postgresql+asyncpg://`` at startup.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Supabase
    supabase_url: str = "http://localhost:54321"
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Postgres (direct connection to Supabase Postgres)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:54322/postgres"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, v: str) -> str:
        return _normalise_db_url(v)

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # GitHub App — required for webhook handling and PR creation.
    # Private key is the PEM contents (not a file path).
    github_app_id: str = ""
    github_private_key: str = ""
    github_webhook_secret: str = ""

    # LLM provider API keys — at least one must be set for agent runs.
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # CORS — comma-separated list of allowed origins.
    # Defaults to ["*"] for local development; restrict in production.
    cors_origins: list[str] = ["*"]

    # Rate limiting — SlowAPI format, e.g. "10/minute", "100/hour".
    run_rate_limit: str = "10/minute"

    # Sentry — leave blank to disable error capture.
    sentry_dsn: str = ""

    # Storage
    storage_bucket: str = "artifacts"

    # App
    debug: bool = True


def get_settings() -> Settings:
    return Settings()
