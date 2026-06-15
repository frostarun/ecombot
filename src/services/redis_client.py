"""Redis cache helpers for eComBot Day 04.

Redis stores short-lived working-memory snapshots and latest-session pointers.
It is not the durable business record; PostgreSQL owns durable history/data.
"""

import json
import logging
from typing import Any

from ..config.settings import settings

log = logging.getLogger(__name__)

_client: Any | None = None


def _get_redis() -> Any:
    global _client
    if _client is None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError(
                "redis is not installed. Run: pip install -r requirements.txt"
            ) from exc

        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
            socket_connect_timeout=3,
        )
    return _client


def save_session_state(session_id: str, state: dict[str, Any]) -> None:
    """Snapshot ADK working memory to Redis with a TTL."""
    try:
        _get_redis().setex(
            f"ecombot:state:{session_id}",
            settings.redis_session_ttl,
            json.dumps(state, default=str),
        )
    except Exception as exc:
        log.warning("Redis state snapshot skipped: %s", exc)


def load_session_state(session_id: str) -> dict[str, Any] | None:
    """Load a cached session-state snapshot, if available."""
    try:
        raw = _get_redis().get(f"ecombot:state:{session_id}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        log.warning("Redis state load skipped: %s", exc)
        return None


def save_session_ref(user_id: str, session_id: str) -> None:
    """Store the latest session id for a user."""
    try:
        _get_redis().setex(
            f"ecombot:session_ref:{user_id}",
            settings.redis_session_ttl,
            session_id,
        )
    except Exception as exc:
        log.warning("Redis session reference skipped: %s", exc)


def load_session_ref(user_id: str) -> str | None:
    """Return the latest session id for a user, if cached."""
    try:
        return _get_redis().get(f"ecombot:session_ref:{user_id}")
    except Exception as exc:
        log.warning("Redis session reference load skipped: %s", exc)
        return None


def check_connection() -> bool:
    """Return True when Redis is reachable."""
    try:
        return bool(_get_redis().ping())
    except Exception:
        return False
