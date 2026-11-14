"""Unit tests for the Postgres TaskStore."""

from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import psycopg
import pytest

from taskboard16_api.tasks import store as store_module
from taskboard16_api.tasks.store import TaskStore


@pytest.fixture()
def task_store(clean_database: str) -> Iterator[TaskStore]:
    s = TaskStore(clean_database)
    try:
        yield s
    finally:
        s.close()


def test_new_store_is_empty(task_store: TaskStore) -> None:
    task_store.ensure_schema()
    assert task_store.list() == []


def test_adds_keep_order_with_distinct_ids(task_store: TaskStore) -> None:
    task_store.add("a", None)
    task_store.add("b", date(2030, 1, 2))
    task_store.add("c", None)
    tasks = task_store.list()
    assert [t.title for t in tasks] == ["a", "b", "c"]
    assert tasks[1].due_date == date(2030, 1, 2)
    assert len({t.id for t in tasks}) == 3


def test_same_transaction_rows_keep_insert_order(
    task_store: TaskStore, clean_database: str
) -> None:
    task_store.ensure_schema()
    with psycopg.connect(clean_database) as conn:  # one transaction: identical created_at
        for i, title in enumerate(["first", "second", "third"]):
            conn.execute(
                "INSERT INTO tasks (id, title) VALUES (%s, %s)",
                (f"00000000-0000-0000-0000-00000000000{9 - i}", title),
            )
    assert [t.title for t in task_store.list()] == ["first", "second", "third"]


def test_ensure_schema_twice_is_idempotent(task_store: TaskStore) -> None:
    task_store.ensure_schema()
    task_store.add("kept", None)
    task_store.ensure_schema()
    assert [t.title for t in task_store.list()] == ["kept"]


def test_ensure_schema_concurrently_from_two_stores(clean_database: str) -> None:
    stores = [TaskStore(clean_database) for _ in range(2)]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda s: s.ensure_schema(), stores))
        assert stores[0].list() == []
    finally:
        for s in stores:
            s.close()


def test_unreachable_database_fails_within_5_seconds() -> None:
    s = TaskStore("postgresql://u:p@127.0.0.1:1/x")
    try:
        start = time.monotonic()
        with pytest.raises(store_module.StorageUnavailable):
            s.add("x", None)
        assert time.monotonic() - start < 5
    finally:
        s.close()


def test_concurrent_adds_lose_none(task_store: TaskStore) -> None:
    task_store.ensure_schema()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: task_store.add(f"t{i}", None), range(100)))
    assert len({t.id for t in task_store.list()}) == 100


def test_ping_is_true_when_reachable(task_store: TaskStore) -> None:
    assert task_store.ping() is True


def test_ping_is_false_and_never_raises_when_unreachable() -> None:
    s = TaskStore("postgresql://u:p@127.0.0.1:1/x")
    try:
        assert s.ping() is False
    finally:
        s.close()


def test_unreachable_database_raises_storage_unavailable() -> None:
    s = TaskStore("postgresql://u:p@127.0.0.1:1/x")
    try:
        with pytest.raises(store_module.StorageUnavailable):
            s.list()
    finally:
        s.close()


def test_get_task_store_returns_singleton() -> None:
    try:
        assert store_module.get_task_store() is store_module.get_task_store()
    finally:
        store_module.close_task_store()
