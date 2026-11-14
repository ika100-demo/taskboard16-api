---
spec_id: 002-store-tasks-in-postgres-so-they-survive
title: Store tasks in Postgres so they survive restarts and are shared by every instance
status: done
priority: P1
shape: service-python
parent: ika100-demo/taskboard16-gitops:001-persistent-tasks-in-postgres-with-a-web
---

# 002 — Store tasks in Postgres so they survive restarts and are shared by every instance

## Problem

The Task API keeps tasks in memory only, so every restart or redeploy of taskboard16-api loses all tasks, and a second replica would see different tasks. The Taskboard web UI is still the starter page, so people can use the taskboard only by calling the API by hand. Now that both components run in dev, the system should keep tasks in a Postgres database and give people a page where they see and create tasks.

## System context

Slice of the system plan `001-persistent-tasks-in-postgres-with-a-web` in `ika100-demo/taskboard16-gitops` for `taskboard16-api` (service-python). The system criteria and the contract below are binding: every criterion of this spec implements one of them and names it: `(system AC-<NNN>.<n>)`.

### System criteria

- **AC-001.1** Given a task created with `POST /tasks` `{"title": "Buy milk", "due_date": "2026-12-01"}`, when every taskboard16-api instance restarts (or is redeployed) and a client sends `GET /tasks`, then the response is 200 and holds that task with the same `id`, `title` and `due_date`.
- **AC-001.2** Given two taskboard16-api instances running against the same database, when a task is created through one of them, then `GET /tasks` answered by either instance holds that task.
- **AC-001.5** Given the start page of the web UI, when a user enters the title "Call Anna" with or without a due date and submits the create form, then within 2 seconds the task appears at the end of the list on the page without a manual reload, the form is cleared, and `GET /tasks` on the API holds the task with that title and due date.
- **AC-001.6** Given the create form, when a user submits a title that is empty, only whitespace or longer than 200 characters, then the form shows "Title must be 1 to 200 characters", keeps the entered values, and no task is created (the list and `GET /tasks` are unchanged).
- **AC-001.7** Given the database is unreachable, when a client sends `GET /tasks` or `POST /tasks`, then the response is 503 within 5 seconds, `GET /ready` answers 503, and no task created during the outage appears once the database is back.

### Contract

Base URL for the web UI: the server-side env var `API_URL` (`http://taskboard16-api` in the cluster). Only the
Next.js server calls the API; the browser talks to the web UI only. All bodies are JSON (`Content-Type:
application/json`), UTF-8. No authentication (system A10).

Task object (unchanged from taskboard16-api spec 001):

| Field | Type | Notes |
|---|---|---|
| `id` | string | opaque, server-assigned (uuid4); never sent by the client |
| `title` | string | 1 to 200 characters after trimming; stored and returned exactly as sent |
| `due_date` | string `YYYY-MM-DD` or `null` | calendar date without time; `null` = no due date |

`GET /tasks`
- `200`: JSON array of task objects, every task, oldest first by creation time, no limit; `[]` when there are none.
- `503`: the database is unreachable (see Errors).

`POST /tasks`
- Request: `{"title": string, "due_date": "YYYY-MM-DD" | null}`; `due_date` optional; unknown fields ignored. The
  web UI sends `due_date: null` when the date field is empty.
- `201`: the created task object; it is committed, so a following `GET /tasks` from any instance holds it as the
  last element.
- `422`: validation failed (title missing, not a string, empty, whitespace-only, over 200 characters after
  trimming; `due_date` not a real `YYYY-MM-DD` date); FastAPI standard body `{"detail": [{"type", "loc", "msg",
  "input", ...}]}`. Nothing is stored.
- `503`: the database is unreachable; nothing is stored, and the task never appears later.

`GET /ready` (taskboard16-api): `200 {"status": "ready"}` when a `SELECT 1` against the database succeeds within 1
second, else `503`. `GET /health` stays `200` regardless of the database.

`/api/ready` and `/api/health` (taskboard16-web): `200` regardless of the Task API, so the start page can show its
error message while the API is down.

Database: one Postgres database (resource `postgres`), reached by taskboard16-api only, via `DATABASE_URL` / `PG*`.
The API owns its schema and creates it idempotently at startup.

### Errors

- Validation errors: `422` with FastAPI's standard `detail` array. The web UI does not parse the array; any `422` on
  `POST /tasks` shows "Title must be 1 to 200 characters" and keeps the entered values (the web UI checks the date
  field is empty or a `YYYY-MM-DD` date picker value, so a date 422 does not occur from the form).
- Storage unavailable: `503` with `{"detail": "Task storage unavailable"}` on `GET /tasks` and `POST /tasks`.
- Any status the contract does not list (including `500`, `502`, `504`), a body that is not the listed JSON shape, a
  connection error or a timeout is treated by the web UI like `503`: on `GET /tasks` the page shows "Tasks could not
  be loaded. Please try again later." instead of the list; on `POST /tasks` the form shows "The task could not be
  saved. Please try again." and keeps the entered values. The web UI never retries a `POST` on its own (no duplicate
  tasks); the user resubmits.
- The web UI logs every failed API call through `@/lib/logger` with the status (or `timeout` / `connection_error`)
  and never shows API error bodies to the user.

### Timeouts

- taskboard16-api to Postgres: connect timeout 2 seconds, statement timeout 2 seconds, pool checkout wait at most 1
  second; on any of them the request answers `503` so that `GET /tasks` and `POST /tasks` answer within 5 seconds
  while the database is down (AC-001.7). Readiness check: 1 second. A `POST` whose transaction did not commit is
  rolled back, so no task created during an outage appears afterwards.
- taskboard16-web to taskboard16-api: 6 seconds per call (`GET /tasks` on page render, `POST /tasks` on submit), longer
  than the API's 5-second bound so the API's `503` arrives first; after that the call counts as failed (see Errors).
  With the API healthy, `POST /tasks` plus updating the list stays under 2 seconds (AC-001.5).
- When the API is down or not ready, Kubernetes stops routing to it (readiness `503`); the web UI keeps serving its
  start page with the error message, and recovers on the next page load or submit with no restart.

### Provided by the system

The gitops part of this plan wires these for this repo; rely on them, do not ask for them again:

- resource `postgres`: env `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`

### Notes for this repo

Storage moves from the in-memory TaskStore to Postgres; connection settings come only from DATABASE_URL / PG*
(injected by the gitops entry's `uses: postgres`). Remove the non-goal "Persistent storage" from the old spec's
scope in the new spec. Ordering is by a server-side creation timestamp plus a tie-breaker (e.g. a bigserial),
never by the uuid. Schema is created on startup idempotently (two instances may start at once). The request
and response contract of POST/GET /tasks is unchanged (system A1). /health stays DB-independent.

## Stories

<!-- As a <persona>, I want <goal>, so that <benefit>. -->

## Acceptance criteria

- **AC-002.1** Given a task created with `POST /tasks` `{"title": "Buy milk", "due_date": "2026-12-01"}`, when the service restarts against the same database and a client sends `GET /tasks`, then the response is 200 and holds that task with the same `id`, `title` and `due_date` (system AC-001.1) (replaces AC-001.7)
- **AC-002.2** Given two service instances using the same `DATABASE_URL`, when a client creates a task with `POST /tasks` through one of them, then `GET /tasks` answered by either instance is 200 and holds that task, and the list is oldest first by creation time (system AC-001.2, AC-001.5)
- **AC-002.3** Given a running service with a reachable database, when a client sends `POST /tasks` with `{"title": "Call Anna"}` and then `GET /tasks`, then the POST answers 201 with `"due_date": null` and the task is the last element of the GET array with that `id`, `title` and `due_date` (system AC-001.5)
- **AC-002.4** Given a running service, when a client sends `POST /tasks` whose `title` is empty, only whitespace or longer than 200 characters after trimming, then the response is 422 and `GET /tasks` returns the same array as before (system AC-001.6)
- **AC-002.5** Given the database is unreachable, when a client sends `GET /tasks` or `POST /tasks`, then the response is 503 with the body `{"detail": "Task storage unavailable"}` within 5 seconds, and `GET /ready` answers 503 (system AC-001.7)
- **AC-002.6** Given the database was unreachable while a client sent `POST /tasks` (answered 503), when the database is reachable again, then `GET /ready` answers 200 and `GET /tasks` does not hold the task sent during the outage (system AC-001.7)
- **AC-002.7** Given an empty database on first start, when the service starts, then it creates its schema itself and `GET /tasks` answers 200 with `[]` (system AC-001.1)

## Non-goals

## Assumptions

<!-- Spec 149: decisions taken by default, approved with the spec. One bullet each: - **A1** <the decision> (other option: <…>; affects AC-…). A revised one is struck through (~~…~~), never deleted. -->

## Open questions

<!-- Only what may not be decided by default (spec 149): security or access, money, destroying or migrating data, or a request too ambiguous to build. Approval is refused while any is open. Strike answered ones (~~…~~) and fold the answer into the criteria. -->

## Changelog

- 2026-11-14 created from the system plan, with its criteria (spec 147)
- 2026-11-14 approved
- 2026-11-14 building
- 2026-11-14 done
