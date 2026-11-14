# Design — 001 Create and list tasks in memory

## Decisions

- Tasks live in a `TaskStore` object (a list guarded by a `threading.Lock`) held at module level in `tasks/store.py` and handed to the routes through the FastAPI dependency `get_task_store`. Sync endpoints run in FastAPI's thread pool, so the lock keeps concurrent `POST`s from losing writes. A restart creates a new, empty store (AC-001.6, AC-001.7); tests simulate a restart by overriding the dependency with a fresh `TaskStore()`.
- Insertion order is the list order, so `GET /tasks` returns oldest first without sorting (AC-001.5, A7).
- `id` is `str(uuid.uuid4())` (A2), assigned by the store, never by the client.
- Validation is done by Pydantic, so invalid input answers FastAPI's standard 422 body (A6). Two fields need custom validators because Pydantic's lax mode is too lenient for the criteria:
  - `title`: strict string (no int-to-str coercion); length 1..200 measured **after** `strip()`, but the value is stored and returned **as sent** (A3, A4, AC-001.3).
  - `due_date`: Pydantic's `date` lax mode accepts Unix timestamps and `YYYY-MM-DDT00:00:00`, which AC-001.4 forbids. A `mode="before"` validator accepts only `None` or a string matching `^\d{4}-\d{2}-\d{2}$` that `date.fromisoformat` parses; anything else raises `ValueError` (422). Past dates are accepted (A5).
- Unknown request fields are ignored (Pydantic default `extra="ignore"`, A8).
- No new dependency, env var, port or probe: no gitops change. Single instance assumed (A9); the in-memory store is feature-local, so no ADR.

## Modules

| Module | Responsibility | New / changed |
|---|---|---|
| `src/taskboard16_api/tasks/__init__.py` | package; re-exports `router` | new |
| `src/taskboard16_api/tasks/store.py` | `Task` dataclass, `TaskStore` (thread-safe, ordered), `get_task_store()` | new |
| `src/taskboard16_api/tasks/schemas.py` | `TaskCreate` (request, validation), `TaskOut` (response) | new |
| `src/taskboard16_api/tasks/router.py` | `APIRouter` with `POST /tasks`, `GET /tasks` | new |
| `src/taskboard16_api/main.py` | `app.include_router(tasks.router)` | changed |

Signatures:

```python
# store.py
@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due_date: date | None

class TaskStore:
    def add(self, title: str, due_date: date | None) -> Task: ...   # assigns uuid4 id, appends
    def list(self) -> list[Task]: ...                                # copy, insertion order

def get_task_store() -> TaskStore: ...   # returns the module-level singleton

# schemas.py
class TaskCreate(BaseModel):
    title: StrictStr                    # validator: 1 <= len(title.strip()) <= 200, returns title unchanged
    due_date: date | None = None        # before-validator: None or ^\d{4}-\d{2}-\d{2}$ + date.fromisoformat

class TaskOut(BaseModel):
    id: str
    title: str
    due_date: date | None               # serialized as "YYYY-MM-DD" or null
```

## Contract

`POST /tasks`
- Request body (JSON): `{"title": str, "due_date": "YYYY-MM-DD" | null}`; `due_date` optional, unknown fields ignored.
- `201` body: `{"id": str, "title": str, "due_date": "YYYY-MM-DD" | null}`; `title` exactly as sent; `due_date` `null` when missing or null (AC-001.1, AC-001.2).
- `422` FastAPI standard validation body `{"detail": [{"type": str, "loc": [...], "msg": str, "input": ..., ...}]}` when:
  - `title` missing, not a string, empty, whitespace-only, or longer than 200 characters after trimming (AC-001.3);
  - `due_date` present, not null, and not a string of the form `YYYY-MM-DD` naming a real calendar date, e.g. `"tomorrow"`, `"2026-02-30"`, `"2026-12-01T10:00:00Z"`, `20261201` (AC-001.4);
  - body is not a JSON object.
  Nothing is stored on a 422.

`GET /tasks`
- `200` body: JSON array of `{"id": str, "title": str, "due_date": "YYYY-MM-DD" | null}`, oldest first, no limit; `[]` when empty (AC-001.5, AC-001.6, AC-001.7).

Test hook (for acceptance tests, not public API): `app.dependency_overrides[taskboard16_api.tasks.store.get_task_store] = lambda: fresh_store` gives an empty store, i.e. the state right after a (re)start.

## Data

In memory only: `TaskStore._tasks: list[Task]`, lost on restart (non-goal: persistence).
