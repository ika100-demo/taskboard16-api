"""Acceptance tests for spec 001 (create and list tasks in memory)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from taskboard16_api.main import app


@pytest.fixture()
def tasks_client() -> Iterator[TestClient]:
    """A client on an app with an empty task store (state right after a start)."""
    try:
        from taskboard16_api.tasks import store
    except ImportError:
        pytest.fail("module taskboard16_api.tasks.store is missing")
    fresh = store.TaskStore()
    app.dependency_overrides[store.get_task_store] = lambda: fresh
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(store.get_task_store, None)


def _listed(client: TestClient) -> list[dict]:
    response = client.get("/tasks")
    assert response.status_code == 200
    return response.json()


def test_create_task_with_due_date_returns_201(tasks_client: TestClient):  # AC-001.1
    response = tasks_client.post("/tasks", json={"title": "Buy milk", "due_date": "2026-12-01"})
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], str)
    assert body["id"]
    assert body["title"] == "Buy milk"
    assert body["due_date"] == "2026-12-01"


def test_create_task_without_due_date_has_null(tasks_client: TestClient):  # AC-001.2
    response = tasks_client.post("/tasks", json={"title": "Call Anna"})
    assert response.status_code == 201
    assert response.json()["due_date"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"due_date": "2026-12-01"},
        {"title": 5},
        {"title": None},
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
    ],
)
def test_invalid_title_is_422_and_not_stored(tasks_client: TestClient, payload: dict):  # AC-001.3
    response = tasks_client.post("/tasks", json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert _listed(tasks_client) == []


def test_title_of_200_characters_is_accepted(tasks_client: TestClient):  # AC-001.3
    response = tasks_client.post("/tasks", json={"title": "x" * 200})
    assert response.status_code == 201


@pytest.mark.parametrize("due", ["tomorrow", "2026-02-30", "2026-12-01T10:00:00Z", 20261201, ""])
def test_invalid_due_date_is_422_and_not_stored(tasks_client: TestClient, due: object):  # AC-001.4
    response = tasks_client.post("/tasks", json={"title": "Bad date", "due_date": due})
    assert response.status_code == 422
    assert _listed(tasks_client) == []


def test_list_returns_tasks_in_creation_order(tasks_client: TestClient):  # AC-001.5
    titles = ["first", "second", "third"]
    for title in titles:
        assert tasks_client.post("/tasks", json={"title": title}).status_code == 201
    tasks = _listed(tasks_client)
    assert [t["title"] for t in tasks] == titles
    for task in tasks:
        assert set(task) >= {"id", "title", "due_date"}
    assert len({t["id"] for t in tasks}) == 3


def test_list_is_empty_initially(tasks_client: TestClient):  # AC-001.6
    response = tasks_client.get("/tasks")
    assert response.status_code == 200
    assert response.json() == []


def test_restart_empties_the_list(tasks_client: TestClient):  # AC-001.7
    assert tasks_client.post("/tasks", json={"title": "gone soon"}).status_code == 201
    assert len(_listed(tasks_client)) == 1
    from taskboard16_api.tasks import store

    restarted = store.TaskStore()
    app.dependency_overrides[store.get_task_store] = lambda: restarted
    assert _listed(TestClient(app)) == []
