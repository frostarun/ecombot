"""Shared settings for the eComBot implementation.

All service endpoints and credentials come from environment variables or
``.env``. Keep secrets out of source files.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
AGENT_DIR = ROOT_DIR / "src" / "agents"
DATA_DIR = ROOT_DIR / "data"
PDF_DIR = DATA_DIR / "pdf"
CHROMA_DIR = ROOT_DIR / ".chroma"

APP_NAME = "ecombot"
MODEL = "openrouter/google/gemini-2.5-flash"
FAST_MODEL = os.getenv("ECOMBOT_FAST_MODEL", MODEL)
DEEP_MODEL = os.getenv("ECOMBOT_DEEP_MODEL", MODEL)
FAST_ROUTE_NAME = os.getenv("ECOMBOT_FAST_ROUTE", "fast-faq")
DEEP_ROUTE_NAME = os.getenv("ECOMBOT_DEEP_ROUTE", "deep-support")
EMBEDDING_MODEL = "openrouter/openai/text-embedding-3-small"
RAG_COLLECTION_NAME = "ecombot_kb"
DEFAULT_INSTRUCTION_VERSION = "v3"

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
LITELLM_PROXY_API_KEY_ENV = "LITELLM_PROXY_API_KEY"

load_dotenv(ROOT_DIR / ".env")


@dataclass
class Settings:
    """Runtime settings read from environment variables."""

    session_backend: str = field(
        default_factory=lambda: os.getenv("SESSION_BACKEND", "database").lower()
    )

    pg_host: str = field(default_factory=lambda: os.getenv("PG_HOST", "localhost"))
    pg_port: int = field(default_factory=lambda: int(os.getenv("PG_PORT", "5432")))
    pg_db: str = field(default_factory=lambda: os.getenv("PG_DB", "ecombot"))
    pg_user: str = field(default_factory=lambda: os.getenv("PG_USER", "ecombot"))
    pg_password: str = field(default_factory=lambda: os.getenv("PG_PASSWORD", "pg_secret"))

    redis_host: str = field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    redis_port: int = field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    redis_password: str = field(
        default_factory=lambda: os.getenv("REDIS_PASSWORD", "redis_secret")
    )
    redis_session_ttl: int = field(
        default_factory=lambda: int(os.getenv("REDIS_SESSION_TTL", "3600"))
    )

    @property
    def pg_dsn(self) -> str:
        """PostgreSQL connection string for the application database."""
        return (
            f"host={self.pg_host} port={self.pg_port} dbname={self.pg_db} "
            f"user={self.pg_user} password={self.pg_password}"
        )

    @property
    def adk_db_url(self) -> str:
        """SQLAlchemy URL for ADK DatabaseSessionService."""
        return (
            f"postgresql+asyncpg://{self.pg_user}:{self.pg_password}"
            f"@{self.pg_host}:{self.pg_port}/{self.pg_db}"
        )

    @property
    def redis_url(self) -> str:
        """Redis URL for cache/session helpers."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}"
        return f"redis://{self.redis_host}:{self.redis_port}"


settings = Settings()
