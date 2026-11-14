"""Smoke tests for AC-001.1 and AC-001.6; they reach the service only through SMOKE_BASE_URL."""

from __future__ import annotations

import uuid

import httpx
import pytest


@pytest.mark.smoke
@pytest.mark.writes
def test_smoke_ac_001_1_create_task(smoke_base_url: str) -> None:  # AC-001.1
    title = f"smoke-{uuid.uuid4()}"
    response = httpx.post(
        smoke_base_url + "/tasks",
        json={"title": title, "due_date": "2026-12-01"},
        timeout=10,
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], str)
    assert body["title"] == title
    assert body["due_date"] == "2026-12-01"


@pytest.mark.smoke
def test_smoke_ac_001_1_rejects_invalid_task_read_only(smoke_base_url: str) -> None:  # AC-001.1
    response = httpx.post(smoke_base_url + "/tasks", json={"title": ""}, timeout=10)
    assert response.status_code == 422


@pytest.mark.smoke
def test_smoke_ac_001_6_list_tasks(smoke_base_url: str) -> None:  # AC-001.6
    # The shared instance may hold tasks, so only status and shape are checked.
    response = httpx.get(smoke_base_url + "/tasks", timeout=10)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
