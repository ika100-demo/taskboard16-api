---
spec_id: 002-store-tasks-in-postgres-so-they-survive
shape: service-python
spec_hash: 34b22893d9ab
summary: Replace the in-memory TaskStore with a Postgres store (psycopg 3 pool), 503 on outage, DB-backed readiness
tasks:
  - id: t1
    title: Store tasks in Postgres with schema at startup, 503 on outage and DB readiness
    files: [pyproject.toml, uv.lock, src/taskboard16_api/db.py, src/taskboard16_api/tasks/store.py, src/taskboard16_api/tasks/schemas.py, src/taskboard16_api/main.py, tests/test_task_store.py, tests/test_task_schemas.py, docs/env-vars.md]
    covers: [AC-002.1, AC-002.2, AC-002.3, AC-002.4, AC-002.5, AC-002.6, AC-002.7]
    parallel_safe: false
    depends_on: []
---

# Plan — 002 Store tasks in Postgres so they survive restarts and are shared by every instance

See [design.md](design.md) for the contract, signatures, schema and test hooks.

One task: every acceptance criterion is HTTP-level and needs the store, the 503 mapping and the lifespan together, so no split would let a task's checks pass on its own.

## t1 — Store tasks in Postgres with schema at startup, 503 on outage and DB readiness

**Files:** pyproject.toml, uv.lock, src/taskboard16_api/db.py, src/taskboard16_api/tasks/store.py, src/taskboard16_api/tasks/schemas.py, src/taskboard16_api/main.py, tests/test_task_store.py, tests/test_task_schemas.py, docs/env-vars.md
**Covers:** AC-002.1, AC-002.2, AC-002.3, AC-002.4, AC-002.5, AC-002.6, AC-002.7
**Goal:** tasks persist in the shared Postgres database, every instance sees the same oldest-first list, and a database outage answers 503 without leaving rows behind, with `/ready` tracking the database.

**Implementation notes:**
- Dependencies: `psycopg[binary]>=3.2`, `psycopg-pool>=3.2` in `dependencies`; `testcontainers[postgres]>=4.8` in the `dev` extra; refresh `uv.lock` (`devbox shell`, then the project's lock workflow; never `pip`/`uv add` directly per CLAUDE.md).
- `db.py`: `database_conninfo()` and `make_pool()` exactly as in design.md (connect 2 s, statement 2 s, `tcp_user_timeout` 2 s, keepalives, checkout 1 s, `check=ConnectionPool.check_connection`, `open=False`).
- `tasks/store.py`: rewrite as the Postgres `TaskStore(conninfo)`; wrap every `psycopg.Error` in `StorageUnavailable`; `add` in one transaction with bound parameters; `list` ordered by `created_at, seq`; `ensure_schema` under `pg_advisory_xact_lock` with a once-per-process flag, retried lazily before operations and in `ping`; lazy singleton `get_task_store()` and `close_task_store()`. Nothing connects at import time.
- `tasks/schemas.py`: reject `"\x00"` in `title` (422); everything else unchanged.
- `main.py`: `lifespan` as in design.md; exception handler `StorageUnavailable` → `JSONResponse(503, {"detail": "Task storage unavailable"})` plus `log.warning("storage_unavailable", error=type(exc).__name__)`; `/ready` takes `TaskStore` via `Depends(get_task_store)` and answers `200 {"status": "ready"}` or `503 {"status": "unavailable"}`; `/health`, `/ping`, `/metrics` unchanged.
- `tasks/router.py` stays as is (the `StoreDep` dependency and handlers already fit); touch it only if mypy requires.
- Never log `DATABASE_URL`, `PGPASSWORD` or task titles.
- `tests/test_task_store.py`: replace the in-memory unit tests with store tests against the `database_url` fixture (empty list, order of three adds incl. same-transaction tie on `seq`, concurrent adds lose none, `ensure_schema` twice and concurrently from two stores, `StorageUnavailable` on a closed port within 5 s, `ping` false/true). `tests/test_task_schemas.py`: add the U+0000 case.
- `docs/env-vars.md`: a "Database" section for `DATABASE_URL` and `PG*` (no defaults; injected by the gitops entry's `uses: postgres`) and `TEST_DATABASE_URL` (tests only).

**Done when:** the acceptance tests for AC-002.1 to AC-002.7 pass (with the spec-001 tests the testers adapted to the new store hook), `tests/test_task_store.py` and `tests/test_task_schemas.py` pass, and `devbox run ci` is green.
