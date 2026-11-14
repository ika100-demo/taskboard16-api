"""Smoke tests for health/ready/ping endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from taskboard16_api.main import app


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_ready(client: TestClient, clean_database: str) -> None:  # AC-002.5
    from taskboard16_api.tasks import store

    s = store.TaskStore(clean_database)
    app.dependency_overrides[store.get_task_store] = lambda: s
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(store.get_task_store, None)
        s.close()
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ping_returns_project_name(client: TestClient) -> None:
    response = client.get("/ping")
    assert response.status_code == 200
    assert response.json() == {"pong": "taskboard16-api"}
