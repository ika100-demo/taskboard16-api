"""Postgres connection settings and pool factory."""

from __future__ import annotations

import os

from psycopg_pool import ConnectionPool

CONNECT_TIMEOUT_S = 2
STATEMENT_TIMEOUT_MS = 2000
POOL_CHECKOUT_TIMEOUT_S = 1.0


def database_conninfo() -> str:
    """The libpq conninfo from DATABASE_URL; empty means libpq reads PG* itself."""
    return os.environ.get("DATABASE_URL", "")


def make_pool(conninfo: str) -> ConnectionPool:
    """A closed pool with the contract's timeouts; nothing connects until it is opened."""
    return ConnectionPool(
        conninfo,
        min_size=1,
        max_size=10,
        open=False,
        timeout=POOL_CHECKOUT_TIMEOUT_S,
        check=ConnectionPool.check_connection,
        kwargs={
            "connect_timeout": CONNECT_TIMEOUT_S,
            "options": f"-c statement_timeout={STATEMENT_TIMEOUT_MS}",
            "tcp_user_timeout": STATEMENT_TIMEOUT_MS,
            "keepalives": 1,
        },
    )
