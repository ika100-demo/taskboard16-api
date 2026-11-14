---
spec_id: 001-create-and-list-tasks-in-memory
shape: service-python
spec_hash: e71cb0057449
summary: In-memory POST /tasks and GET /tasks with strict title and due_date validation
tasks:
- id: t3
  title: Expose POST /tasks and GET /tasks and wire the router into the app
  files: [src/taskboard16_api/tasks/router.py, src/taskboard16_api/tasks/__init__.py, src/taskboard16_api/main.py, src/taskboard16_api/tasks/store.py,
    tests/test_task_store.py, src/taskboard16_api/tasks/schemas.py, tests/test_task_schemas.py]
  covers: [AC-001.1, AC-001.2, AC-001.3, AC-001.4, AC-001.5, AC-001.6, AC-001.7]
  parallel_safe: false
  depends_on: []
  done: true
---

# Plan — 001 Create and list tasks in memory

See [design.md](design.md) for the contract and signatures.

## t3 — Expose POST /tasks and GET /tasks and wire the router into the app

**Files:** src/taskboard16_api/tasks/router.py, src/taskboard16_api/tasks/__init__.py, src/taskboard16_api/main.py, src/taskboard16_api/tasks/store.py, tests/test_task_store.py, src/taskboard16_api/tasks/schemas.py, tests/test_task_schemas.py
**Covers:** AC-001.1, AC-001.2, AC-001.3, AC-001.4, AC-001.5, AC-001.6, AC-001.7
**Goal:** the HTTP contract of design.md, end to end.

**Implementation notes:**
- `router = APIRouter(tags=["tasks"])`; `POST /tasks` (`status_code=201`, `response_model=TaskOut`) takes `TaskCreate` and `store: TaskStore = Depends(get_task_store)`, calls `store.add`; `GET /tasks` (`response_model=list[TaskOut]`) returns `store.list()`.
- Sync (`def`) handlers; the store's lock covers thread-pool concurrency.
- `tasks/__init__.py` re-exports `router`.
- `main.py`: `app.include_router(tasks.router)` after the middleware setup; leave health, ready, ping, metrics unchanged.
- Log one structured event per created task (`task_created`, `task_id`), never the title.

**Done when:** all acceptance tests for AC-001.1 to AC-001.7 pass, including the smoke tests, and `devbox run ci` is green.

**Merged from t1 — Add thread-safe in-memory TaskStore** (t1 acceptance tests (AC-001.5-7) can only pass once t3 adds the /tasks routes; all failures are 404):

**Files:** src/taskboard16_api/tasks/store.py, tests/test_task_store.py
**Covers:** AC-001.5, AC-001.6, AC-001.7
**Goal:** the ordered, thread-safe in-memory store every route reads and writes.

**Implementation notes:**
- `Task` frozen dataclass (`id: str`, `title: str`, `due_date: date | None`).
- `TaskStore` with a private `list[Task]` and a `threading.Lock`; `add(title, due_date)` assigns `str(uuid.uuid4())`, appends under the lock, returns the `Task`; `list()` returns a copy in insertion order.
- Module-level singleton and `get_task_store() -> TaskStore` returning it (the dependency the router uses and tests override).
- Do not create `tasks/__init__.py` (t3 owns it, so t1 and t2 can run in parallel); until then `taskboard16_api.tasks` imports as a namespace subpackage, which pytest and mypy handle.
- Unit tests: a new store is empty; three adds come back in order with distinct ids; concurrent adds from threads lose none.

**Done when:** `tests/test_task_store.py` passes and `devbox run quality` is green.

**Merged from t2 — Add TaskCreate and TaskOut schemas with validation** (t2 acceptance tests (AC-001.1-4) can only pass once t3 adds the /tasks routes; all failures are 404):

**Files:** src/taskboard16_api/tasks/schemas.py, tests/test_task_schemas.py
**Covers:** AC-001.1, AC-001.2, AC-001.3, AC-001.4
**Goal:** request and response models that enforce exactly the validation rules of the contract.

**Implementation notes:**
- `TaskCreate.title: StrictStr` with an after-validator: `1 <= len(v.strip()) <= 200`, return `v` unchanged (A3, A4).
- `TaskCreate.due_date: date | None = None` with a `mode="before"` validator: `None` passes; a `str` must match `^\d{4}-\d{2}-\d{2}$` and parse with `date.fromisoformat` (catches `2026-02-30`); any other type or value raises `ValueError`.
- Default `extra="ignore"` (A8).
- `TaskOut(id: str, title: str, due_date: date | None)`; serialises the date as `YYYY-MM-DD`.
- Do not create `tasks/__init__.py` (see t1).
- Unit tests for each 422 case in AC-001.3 and AC-001.4 (incl. integer timestamp and `T00:00:00` suffix), title preserved with surrounding spaces, 200 characters after trim accepted, 201 rejected.

**Done when:** `tests/test_task_schemas.py` passes and `devbox run quality` is green.

