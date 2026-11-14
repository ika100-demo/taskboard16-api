"""Acceptance tests for spec 002 (tasks stored in Postgres)."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable, Iterator
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient

from taskboard16_api.main import app

UNAVAILABLE = {"detail": "Task storage unavailable"}


def _store_module():
    try:
        from taskboard16_api.tasks import store
    except ImportError:
        pytest.fail("module taskboard16_api.tasks.store is missing")
    return store


class Instances:
    """Builds TaskStores on a database, injects them into the app and closes them at the end."""

    def __init__(self) -> None:
        self.stores: list = []

    def make(self, url: str):
        store = _store_module()
        s = store.TaskStore(url)
        self.stores.append(s)
        return s

    def use(self, s) -> TestClient:
        store = _store_module()
        app.dependency_overrides[store.get_task_store] = lambda: s
        return TestClient(app, raise_server_exceptions=False)

    def close(self) -> None:
        store = _store_module()
        app.dependency_overrides.pop(store.get_task_store, None)
        for s in self.stores:
            s.close()


@pytest.fixture()
def instances() -> Iterator[Instances]:
    inst = Instances()
    try:
        yield inst
    finally:
        inst.close()


class DbProxy:
    """A threaded TCP forwarder on a fixed local port; stop() makes the database unreachable."""

    def __init__(self, target_host: str, target_port: int) -> None:
        self.target = (target_host, target_port)
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self._listener: socket.socket | None = None
        self._conns: list[socket.socket] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        listener = socket.socket()
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", self.port))
        listener.listen(32)
        self._listener = listener
        threading.Thread(target=self._accept, args=(listener,), daemon=True).start()

    def _accept(self, listener: socket.socket) -> None:
        while True:
            try:
                client, _ = listener.accept()
                upstream = socket.create_connection(self.target, timeout=5)
            except OSError:
                if self._listener is not listener:
                    return
                continue
            upstream.settimeout(None)
            with self._lock:
                self._conns += [client, upstream]
            threading.Thread(target=self._pipe, args=(client, upstream), daemon=True).start()
            threading.Thread(target=self._pipe, args=(upstream, client), daemon=True).start()

    @staticmethod
    def _pipe(src: socket.socket, dst: socket.socket) -> None:
        try:
            while data := src.recv(65536):
                dst.sendall(data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try:
                    s.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def stop(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
        with self._lock:
            conns, self._conns = self._conns, []
        for c in conns:
            try:
                c.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            c.close()


@pytest.fixture()
def db_proxy(clean_database: str) -> Iterator[tuple[DbProxy, str]]:
    parts = urlsplit(clean_database)
    proxy = DbProxy(parts.hostname or "127.0.0.1", parts.port or 5432)
    userinfo = parts.netloc.rpartition("@")[0]
    netloc = f"{userinfo}@127.0.0.1:{proxy.port}" if userinfo else f"127.0.0.1:{proxy.port}"
    proxy.start()
    try:
        yield proxy, urlunsplit(parts._replace(netloc=netloc))
    finally:
        proxy.stop()


def _listed(client: TestClient) -> list[dict]:
    response = client.get("/tasks")
    assert response.status_code == 200
    return response.json()


def _timed(call: Callable[[], object]):
    start = time.monotonic()
    response = call()
    return response, time.monotonic() - start


def test_task_survives_restart(clean_database: str, instances: Instances):  # AC-002.1
    first = instances.use(instances.make(clean_database))
    created = first.post("/tasks", json={"title": "Buy milk", "due_date": "2026-12-01"})
    assert created.status_code == 201
    instances.stores[0].close()

    restarted = instances.use(instances.make(clean_database))
    tasks = _listed(restarted)
    assert len(tasks) == 1
    assert tasks[0]["id"] == created.json()["id"]
    assert tasks[0]["title"] == "Buy milk"
    assert tasks[0]["due_date"] == "2026-12-01"


def test_two_instances_share_tasks(clean_database: str, instances: Instances):  # AC-002.2
    a = instances.make(clean_database)
    b = instances.make(clean_database)
    titles = ["one", "two", "three", "four"]
    ids = []
    for i, title in enumerate(titles):
        writer = instances.use(a if i % 2 == 0 else b)
        response = writer.post("/tasks", json={"title": title})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    for reader in (a, b):
        tasks = _listed(instances.use(reader))
        assert [t["title"] for t in tasks] == titles
        assert [t["id"] for t in tasks] == ids


def test_null_due_date_task_is_last(clean_database: str, instances: Instances):  # AC-002.3
    c = instances.use(instances.make(clean_database))
    assert c.post("/tasks", json={"title": "earlier"}).status_code == 201
    response = c.post("/tasks", json={"title": "Call Anna"})
    assert response.status_code == 201
    created = response.json()
    assert created["due_date"] is None
    last = _listed(c)[-1]
    assert last["id"] == created["id"]
    assert last["title"] == "Call Anna"
    assert last["due_date"] is None


@pytest.mark.parametrize("title", ["", "   ", "\t\n ", "x" * 201, " " + "x" * 201 + " "])
def test_invalid_title_is_422_and_list_unchanged(
    clean_database: str, instances: Instances, title: str
):  # AC-002.4
    c = instances.use(instances.make(clean_database))
    assert c.post("/tasks", json={"title": "kept"}).status_code == 201
    before = _listed(c)
    response = c.post("/tasks", json={"title": title})
    assert response.status_code == 422
    assert _listed(c) == before


def test_unreachable_db_answers_503(instances: Instances):  # AC-002.5
    c = instances.use(instances.make("postgresql://u:p@127.0.0.1:1/x"))
    for call in (
        lambda: c.get("/tasks"),
        lambda: c.post("/tasks", json={"title": "nobody home"}),
        lambda: c.get("/ready"),
    ):
        response, elapsed = _timed(call)
        assert response.status_code == 503
        assert elapsed < 5
    assert c.get("/tasks").json() == UNAVAILABLE
    assert c.post("/tasks", json={"title": "nobody home"}).json() == UNAVAILABLE


def test_database_going_away_answers_503_within_5s(
    db_proxy: tuple[DbProxy, str], instances: Instances
):  # AC-002.5
    proxy, url = db_proxy
    c = instances.use(instances.make(url))
    assert c.post("/tasks", json={"title": "while up"}).status_code == 201
    assert c.get("/ready").status_code == 200

    proxy.stop()

    response, elapsed = _timed(lambda: c.get("/tasks"))
    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert elapsed < 5
    response, elapsed = _timed(lambda: c.post("/tasks", json={"title": "during outage"}))
    assert response.status_code == 503
    assert response.json() == UNAVAILABLE
    assert elapsed < 5
    assert c.get("/ready").status_code == 503


def test_recovery_after_outage_without_lost_task_leak(
    db_proxy: tuple[DbProxy, str], instances: Instances
):  # AC-002.6
    proxy, url = db_proxy
    c = instances.use(instances.make(url))
    assert c.post("/tasks", json={"title": "before"}).status_code == 201

    proxy.stop()
    assert c.post("/tasks", json={"title": "during outage"}).status_code == 503
    proxy.start()

    assert c.get("/ready").status_code == 200
    titles = [t["title"] for t in _listed(c)]
    assert "during outage" not in titles
    assert titles == ["before"]


def test_schema_created_at_startup(clean_database: str, instances: Instances):  # AC-002.7
    import psycopg

    instances.use(instances.make(clean_database))
    with TestClient(app, raise_server_exceptions=False) as started:
        with psycopg.connect(clean_database) as conn:
            row = conn.execute("SELECT to_regclass('public.tasks')").fetchone()
        assert row is not None and row[0] is not None
        response = started.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []
