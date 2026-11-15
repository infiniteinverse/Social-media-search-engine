"""Database helpers: a small connection pool plus a cursor context manager.

Every query in this project is executed with bound parameters
(psycopg2 `%s` placeholders) -- never string formatting.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_pool: ThreadedConnectionPool | None = None


def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env first.")
    return dsn


def get_conn():
    """Plain, un-pooled connection (used by the ingestion script)."""
    return psycopg2.connect(_dsn())


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(1, 8, _dsn())
    return _pool


@contextmanager
def cursor():
    """Yield a dict-cursor from the pool; commit on success, roll back on error."""
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)
