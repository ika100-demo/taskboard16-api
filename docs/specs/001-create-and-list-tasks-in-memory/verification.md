# Verification — 001 Create and list tasks in memory

**Result:** pass
**Commit:** 74e6a65 · **Base:** 748a046 · **Trace:** 7/7 criteria named by tests (smoke: AC-001.1, AC-001.6)

| Criterion | Verdict | Tests | Implementation | Notes |
|---|---|---|---|---|
| AC-001.1 | met | `tests/test_tasks.py::test_create_task_with_due_date_returns_201`; smoke `tests/test_smoke_tasks.py::test_smoke_ac_001_1_create_task` (`writes`) | `src/taskboard16_api/tasks/router.py:16-20`, `src/taskboard16_api/tasks/store.py:23-27` (uuid4 id), `src/taskboard16_api/tasks/schemas.py:34-37` | asserts 201, non-empty string `id`, `title == "Buy milk"`, `due_date == "2026-12-01"` |
| AC-001.2 | met | `tests/test_tasks.py::test_create_task_without_due_date_has_null` | `src/taskboard16_api/tasks/schemas.py:15`, `:27-28` | asserts 201 and `due_date is None` |
| AC-001.3 | met | `tests/test_tasks.py::test_invalid_title_is_422_and_not_stored` (missing x2, `5`, `None`, `""`, `"   "`, 201 chars), `::test_title_of_200_characters_is_accepted` | `src/taskboard16_api/tasks/schemas.py:14` (StrictStr), `:17-22` (1..200 after strip, value returned unchanged) | each case asserts 422 and `GET /tasks == []`; 200-char boundary asserted 201 |
| AC-001.4 | met | `tests/test_tasks.py::test_invalid_due_date_is_422_and_not_stored` (`"tomorrow"`, `"2026-02-30"`, `"2026-12-01T10:00:00Z"`, `20261201`, `""`) | `src/taskboard16_api/tasks/schemas.py:9`, `:24-31` (regex + `date.fromisoformat`, non-strings rejected) | all three spec examples covered; each asserts 422 and empty list |
| AC-001.5 | met | `tests/test_tasks.py::test_list_returns_tasks_in_creation_order` | `src/taskboard16_api/tasks/store.py:23-31` (append under lock, copy in insertion order), `src/taskboard16_api/tasks/router.py:23-25` | asserts 200, exact title order of the three, keys `id/title/due_date` on each, 3 distinct ids |
| AC-001.6 | met | `tests/test_tasks.py::test_list_is_empty_initially`; smoke `tests/test_smoke_tasks.py::test_smoke_ac_001_6_list_tasks` (read-only) | `src/taskboard16_api/tasks/store.py:19-21`, `:34-38`, `src/taskboard16_api/tasks/router.py:23-25` | acceptance test asserts `== []`; the smoke test checks only 200 + list, by necessity on a shared instance (comment in test) |
| AC-001.7 | met | `tests/test_tasks.py::test_restart_empties_the_list` | `src/taskboard16_api/tasks/store.py:34-38` (module-level in-memory singleton, new on process start) | restart simulated by overriding `get_task_store` with a fresh `TaskStore()`, the hook `design.md` defines; asserts 1 task before, `[]` after |

## Non-goals

No persistence, no single-task read/update/delete, no filtering/sorting/pagination, no auth, no fields beyond `title` and `due_date`. No template-owned changes: `main.py` only adds `tasks` to an import and `app.include_router(tasks.router)` (`src/taskboard16_api/main.py:13`, `:26`); health, ready, ping, metrics unchanged. ✔

## Deviations from the plan

- Tasks t1 and t2 merged into t3 (`cplat plan merge`, recorded in `plan.md`) because their acceptance tests could only pass once routes existed; acceptable, t3 `done: true` covers all seven criteria.
- `tests/test_tasks.py` and `tests/test_smoke_tasks.py` are in no task's `files`; acceptable, they are the frozen acceptance tests from the red commit (`e07a3aa`, review fix `f2ae4e0`).
- `docs/specs/.../spec.md`, `plan.md`, `design.md` changed; acceptable, spec status/changelog and planning artefacts.

## Contract

Matches `design.md`: `POST /tasks` 201 with `TaskOut`, 422 FastAPI standard body via Pydantic (`detail` list asserted in AC-001.3 test), `GET /tasks` 200 array oldest first; `Task`/`TaskStore`/`get_task_store`/`TaskCreate`/`TaskOut` signatures as specified; unknown fields ignored (Pydantic default); `task_created` log with `task_id` only, no title (`router.py:19`). ✔

## Notes

- `tests/test_smoke_tasks.py::test_smoke_ac_001_6_list_tasks` cannot assert `[]` against a shared deployed instance; the criterion is fully asserted by `tests/test_tasks.py::test_list_is_empty_initially`, so not counted as TEST LOOSER.
- `_DATE_RE` uses `$`, which in Python also matches before a trailing `\n`; `date.fromisoformat` then rejects such a value, so it still answers 422. No change needed.

## Mutation check (report only)

11 of 14 mutants of the changed code were caught by the acceptance tests (79 %; spec 152, report only).

Survived (a test that names the criterion would fail if it checked this):
- `src/taskboard16_api/tasks/schemas.py:20 1 → 2`
- `src/taskboard16_api/tasks/store.py:38 return value → None`
- `src/taskboard16_api/tasks/store.py:9 True → False`
