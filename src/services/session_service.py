"""ADK Runner/session factory for eComBot Day 04."""

import logging
import importlib.util
import sys
import uuid

from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService, InMemorySessionService

from ..config.settings import APP_NAME, settings
from .redis_client import save_session_ref

try:
    from adk_extra_services.sessions import RedisSessionService
except ImportError:
    RedisSessionService = None

log = logging.getLogger(__name__)


def get_session_service():
    """Return the configured ADK session service.

    ``SESSION_BACKEND=database`` uses ADK DatabaseSessionService with
    PostgreSQL. ``SESSION_BACKEND=redis`` uses the trainer's
    adk-extra-services RedisSessionService. ``SESSION_BACKEND=memory`` is a
    local fallback for tests.
    """
    if settings.session_backend == "memory":
        return InMemorySessionService()

    if settings.session_backend == "redis":
        if RedisSessionService is None:
            raise RuntimeError(
                "SESSION_BACKEND=redis requires adk-extra-services. "
                "Run `pip install -r requirements.txt`."
            )
        try:
            return RedisSessionService(redis_url=settings.redis_url)
        except Exception as exc:
            raise RuntimeError(
                "Cannot create Redis-backed ADK session service. "
                "Start Redis with `docker compose up -d redis` and confirm "
                ".env Redis values."
            ) from exc

    if settings.session_backend != "database":
        log.warning(
            "Unsupported SESSION_BACKEND=%s; falling back to database",
            settings.session_backend,
        )

    if importlib.util.find_spec("asyncpg") is None:
        raise RuntimeError(
            "DatabaseSessionService requires asyncpg, but asyncpg is not "
            f"installed in the active Python interpreter: {sys.executable}. "
            "Activate the adk-june .venv or install requirements with that "
            "same interpreter."
        )

    try:
        return DatabaseSessionService(db_url=settings.adk_db_url)
    except Exception as exc:
        raise RuntimeError(
            "Cannot create PostgreSQL-backed ADK session service. "
            "Run `pip install -r requirements.txt`, start Postgres with "
            "`docker compose up -d postgres`, and confirm .env database values. "
            f"Detail: {exc}"
        ) from exc


async def make_runner(
    agent,
    user_id: str | None = None,
    session_id: str | None = None,
    session_service=None,
) -> tuple[Runner, str, str]:
    """Create a Runner and create/reuse the requested session."""
    session_service = session_service or get_session_service()
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    if user_id is None:
        user_id = f"user-{uuid.uuid4().hex[:6]}"

    if session_id is None:
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
    else:
        existing = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )
        if existing is None:
            await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )

    save_session_ref(user_id, session_id)
    return runner, user_id, session_id
