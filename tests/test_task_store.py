"""Unit tests for the in-memory TaskStore."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from taskboard16_api.tasks.store import TaskStore, get_task_store


def test_new_store_is_empty() -> None:
    assert TaskStore().list() == []


def test_adds_keep_order_with_distinct_ids() -> None:
    store = TaskStore()
    store.add("a", None)
    store.add("b", date(2030, 1, 2))
    store.add("c", None)
    tasks = store.list()
    assert [t.title for t in tasks] == ["a", "b", "c"]
    assert tasks[1].due_date == date(2030, 1, 2)
    assert len({t.id for t in tasks}) == 3


def test_list_returns_copy() -> None:
    store = TaskStore()
    store.add("a", None)
    store.list().clear()
    assert len(store.list()) == 1


def test_concurrent_adds_lose_none() -> None:
    store = TaskStore()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: store.add(f"t{i}", None), range(200)))
    assert len({t.id for t in store.list()}) == 200


def test_get_task_store_returns_singleton() -> None:
    assert get_task_store() is get_task_store()
