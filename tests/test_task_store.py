"""Unit tests for the Postgres TaskStore."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date

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
