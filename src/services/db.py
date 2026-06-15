"""PostgreSQL access layer for eComBot Day 04.

The rest of the application uses this module instead of importing a database
driver directly. Keep driver details here so tools can stay focused on business
logic.
"""

import logging
from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Generator

from ..config.settings import settings

log = logging.getLogger(__name__)


def _load_database_driver():
    """Load the installed PostgreSQL driver and dictionary row factory."""
    try:
        import psycopg as postgres_driver
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL database driver is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc

    return postgres_driver, dict_row


@contextmanager
def _database_connection() -> Generator[Any, None, None]:
    """Open a database connection and handle commit/rollback consistently."""
    postgres_driver, dictionary_rows = _load_database_driver()

    with postgres_driver.connect(
        settings.pg_dsn,
        row_factory=dictionary_rows,
    ) as connection:
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def query_one(
    sql: str,
    params: Sequence[Any] | None = None,
) -> dict[str, Any] | None:
    """Run a SELECT and return one row as a dict."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return dict(row) if row else None


def query_all(
    sql: str,
    params: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """Run a SELECT and return all rows as dicts."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]


def execute(
    sql: str,
    params: Sequence[Any] | None = None,
) -> int:
    """Run INSERT/UPDATE/DELETE and return the affected row count."""
    with _database_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.rowcount


def check_connection() -> bool:
    """Return True when PostgreSQL is reachable."""
    try:
        with _database_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        return True
    except Exception as exc:
        log.warning("PostgreSQL health check failed: %s", exc)
        return False
