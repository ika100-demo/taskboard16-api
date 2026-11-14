# Verification — 002 Store tasks in Postgres so they survive restarts and are shared by every instance

**Result:** pass
**Commit:** f91ce68 · **Base:** 0f66d96 · **Trace:** 7/7 criteria named by tests

| Criterion | Verdict | Tests | Implementation | Notes |
|---|---|---|---|---|
| AC-002.1 | met | `tests/test_task_persistence.py::test_task_survives_restart` | `src/taskboard16_api/tasks/store.py:72`, `src/taskboard16_api/tasks/store.py:85` | posts `{"title": "Buy milk", "due_date": "2026-12-01"}`, closes the store, builds a new `TaskStore` on the same DB; asserts 200, one task, same `id`, `title`, `due_date` |
| AC-002.2 | met | `tests/test_task_persistence.py::test_two_instances_share_tasks` | `src/taskboard16_api/tasks/store.py:90` (`ORDER BY created_at, seq`), `src/taskboard16_api/tasks/store.py:19` | 10 tasks written alternately through two stores; each reader gets 200 and the exact titles and ids in creation order |
| AC-002.3 | met | `tests/test_task_persistence.py::test_null_due_date_task_is_last` | `src/taskboard16_api/tasks/router.py:16`, `src/taskboard16_api/tasks/store.py:72` | asserts 201, `due_date` null, and the last GET element has that `id`, `title`, `due_date` |
| AC-002.4 | met | `tests/test_task_persistence.py::test_invalid_title_is_422_and_list_unchanged` (5 params: empty, spaces, tab/newline, 201 chars, 201 chars padded) | `src/taskboard16_api/tasks/schemas.py:19-24` | asserts 422 and the GET array equals the one before |
| AC-002.5 | met | `tests/test_task_persistence.py::test_unreachable_db_answers_503`, `::test_database_going_away_answers_503_within_5s`; `tests/test_health.py::test_ready_returns_ready` (ready path) | `src/taskboard16_api/main.py:59-62`, `src/taskboard16_api/main.py:65-70`, `src/taskboard16_api/db.py:19-34`, `src/taskboard16_api/tasks/store.py:81`, `:92`, `:96-104` | closed port and a proxied DB that is cut: GET and POST 503 with exact body `{"detail": "Task storage unavailable"}` in < 5 s, `/ready` 503 |
| AC-002.6 | met | `tests/test_task_persistence.py::test_recovery_after_outage_without_lost_task_leak` | `src/taskboard16_api/tasks/store.py:75-82` (one transaction, rollback on error), `src/taskboard16_api/db.py:27` (`check_connection`) | POST during outage 503; after the proxy is back `/ready` reaches 200 and the list is exactly `["before"]` |
| AC-002.7 | met | `tests/test_task_persistence.py::test_schema_created_at_startup` | `src/taskboard16_api/main.py:30-39`, `src/taskboard16_api/tasks/store.py:57-70` | table dropped; lifespan alone creates `public.tasks` (checked via `to_regclass` before any request), then GET 200 `[]` |

## Non-goals

The spec lists none. No template-owned layout (header, footer, navigation) applies to this service; no unrelated endpoints changed (`/health`, `/ping`, `/metrics` unchanged, `src/taskboard16_api/main.py:53-82`). ✔

## Deviations from the plan

- `tests/conftest.py`, `tests/test_health.py`, `tests/test_tasks.py`, `tests/test_task_persistence.py` are in no task's `files`: the acceptance tests and the spec-001 test adaptation the design assigns to the testers (design "Test hooks"); acceptable.
- `docs/adr/001-postgres-storage-psycopg.md`, `docs/adr/README.md`: the ADR design.md calls for; acceptable.
- `docs/backlog.md` (generated index) and `docs/specs/001-.../spec.md` (AC-001.7 struck as superseded by AC-002.1, changelog line): acceptable bookkeeping. Spec 001's non-goal "Persistent storage; tasks are lost on restart (AC-001.7)" is still listed although the system note asks to drop it; documentation only, acceptable, worth a follow-up edit.
- `src/taskboard16_api/tasks/router.py` unchanged, as planned. Task t1 is `done: true`.

## Contract

Matches `design.md`: 503 body and `/ready` bodies (`{"status": "ready"}` / `{"status": "unavailable"}`), timeouts (connect 2 s, statement 2000 ms, `tcp_user_timeout`, keepalives, checkout 1 s, ping 1 s), schema and ordering, `DATABASE_URL`/`PG*` only (`src/taskboard16_api/db.py:14-16`). The U+0000 title rejection (`src/taskboard16_api/tasks/schemas.py:22`) is the documented design departure. ✔

## Suppressions in acceptance tests

None. (`# noqa: N818` at `src/taskboard16_api/tasks/store.py:36` is in production code, named rule, justified by the design's class name.)

## Mutation check (report only)

11 of 20 mutants of the changed code were caught by the acceptance tests (55 %; spec 152, report only).

Survived (a test that names the criterion would fail if it checked this):
- `src/taskboard16_api/db.py:9 2 → 3`
- `src/taskboard16_api/db.py:10 2000 → 2001`
- `src/taskboard16_api/db.py:23 1 → 2`
- `src/taskboard16_api/db.py:25 False → True`
- `src/taskboard16_api/db.py:32 1 → 2`
- `src/taskboard16_api/tasks/store.py:15 7002002002 → 7002002003`
- `src/taskboard16_api/tasks/store.py:116 return value → None`
- `src/taskboard16_api/tasks/store.py:114 Is → IsNot`
- `src/taskboard16_api/tasks/store.py:103 return value → None`
