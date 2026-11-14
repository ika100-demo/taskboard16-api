"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from taskboard16_api.main import app


@pytest.fixture()
def client() -> TestClient:
    """A TestClient for the FastAPI application."""
    return TestClient(app)


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A driver-less Postgres URI: TEST_DATABASE_URL, else a throwaway testcontainer."""
    configured = os.environ.get("TEST_DATABASE_URL")
    if configured:
        yield configured
        return
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.fail("testcontainers[postgres] is missing and TEST_DATABASE_URL is unset")
    with PostgresContainer("postgres:16-alpine") as container:
        url = container.get_connection_url()
        yield url.replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.fixture()
def clean_database(database_url: str) -> str:
    """The database URL with table `tasks` dropped, so each test starts empty."""
    try:
        import psycopg
    except ImportError:
        pytest.fail("psycopg is missing: the Postgres storage dependency is not installed")
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS tasks")
    return database_url
