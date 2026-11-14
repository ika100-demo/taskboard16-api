"""Postgres-backed task store."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg_pool import ConnectionPool

from ..db import database_conninfo, make_pool

_SCHEMA_LOCK_KEY = 7_002_002_002
_PING_TIMEOUT_S = 1.0

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    seq        bigserial   PRIMARY KEY,
    id         uuid        NOT NULL UNIQUE,
    title      text        NOT NULL,
    due_date   date        NULL,
    created_at timestamptz NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due_date: date | None


class StorageUnavailable(Exception):  # noqa: N818 - name fixed by the design contract
    """The database is unreachable or a statement failed."""


class TaskStore:
    """Tasks in Postgres, shared by every instance."""

    def __init__(self, conninfo: str) -> None:
        self._pool: ConnectionPool = make_pool(conninfo)
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    def open(self) -> None:
        try:
            self._pool.open(wait=False)
        except psycopg.Error as exc:
            raise StorageUnavailable from exc

    def close(self) -> None:
        self._pool.close()

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        self.open()
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                with self._pool.connection() as conn:
                    conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_KEY,))
                    conn.execute(_CREATE_TABLE)
            except psycopg.Error as exc:
                raise StorageUnavailable from exc
            self._schema_ready = True

    def add(self, title: str, due_date: date | None) -> Task:
        self.ensure_schema()
        task = Task(id=str(uuid.uuid4()), title=title, due_date=due_date)
        try:
            with self._pool.connection() as conn:
                conn.execute(
                    "INSERT INTO tasks (id, title, due_date) VALUES (%s, %s, %s)",
                    (task.id, task.title, task.due_date),
                )
        except psycopg.Error as exc:
            raise StorageUnavailable from exc
        return task

    def list(self) -> list[Task]:
        self.ensure_schema()
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(
                    "SELECT id, title, due_date FROM tasks ORDER BY created_at, seq"
                ).fetchall()
        except psycopg.Error as exc:
            raise StorageUnavailable from exc
        return [Task(id=str(r[0]), title=r[1], due_date=r[2]) for r in rows]

    def ping(self) -> bool:
        try:
            self.open()
            with self._pool.connection(timeout=_PING_TIMEOUT_S) as conn:
                conn.execute("SELECT 1")
            self.ensure_schema()
        except (psycopg.Error, StorageUnavailable):
            return False
        return True


_store: TaskStore | None = None
_store_lock = threading.Lock()


def get_task_store() -> TaskStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = TaskStore(database_conninfo())
        return _store


def close_task_store() -> None:
    global _store
    with _store_lock:
        store, _store = _store, None
    if store is not None:
        store.close()
