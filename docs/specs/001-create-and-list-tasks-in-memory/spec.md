---
spec_id: 001-create-and-list-tasks-in-memory
title: Create and list tasks in memory
status: draft
priority: P1
shape: service-python
---

# 001 — Create and list tasks in memory

## Problem

The Task API has no tasks yet: it answers only health, readiness, ping and metrics. Clients of the taskboard cannot record what needs doing or see it again. This first feature gives them the smallest useful core, creating a task with a title and an optional due date and listing all tasks. Tasks live in the service's memory only, so the API can be used and tested before any storage is chosen.

## Stories

As a taskboard user, I want to create a task with a title and, if I like, a due date, so that I can write down what needs doing.

As a taskboard user, I want to list all tasks, so that I can see everything I recorded.

## Acceptance criteria

- **AC-001.1** Given a running service, when a client sends `POST /tasks` with `{"title": "Buy milk", "due_date": "2026-12-01"}`, then the response is 201 with a JSON body holding a server-assigned string `id`, `"title": "Buy milk"` and `"due_date": "2026-12-01"`. (smoke)
- **AC-001.2** Given a running service, when a client sends `POST /tasks` with only `{"title": "Call Anna"}`, then the response is 201 and the body holds `"due_date": null`.
- **AC-001.3** Given a running service, when a client sends `POST /tasks` whose `title` is missing, not a string, empty, only whitespace, or longer than 200 characters, then the response is 422, and the task does not appear in `GET /tasks`.
- **AC-001.4** Given a running service, when a client sends `POST /tasks` whose `due_date` is not a calendar date in the form `YYYY-MM-DD` (for example `"tomorrow"`, `"2026-02-30"` or `"2026-12-01T10:00:00Z"`), then the response is 422, and the task does not appear in `GET /tasks`.
- **AC-001.5** Given three tasks created one after another, when a client sends `GET /tasks`, then the response is 200 with a JSON array of those three tasks, each with `id`, `title` and `due_date`, in the order they were created, and every `id` is distinct.
- **AC-001.6** Given no task has been created since the service started, when a client sends `GET /tasks`, then the response is 200 with an empty JSON array `[]`. (smoke)
- **AC-001.7** Given tasks were created, when the service restarts and a client sends `GET /tasks`, then the response is 200 with `[]`.

## Non-goals

- Persistent storage; tasks are lost on restart (AC-001.7).
- Reading, updating, completing or deleting a single task.
- Filtering, sorting options, search or pagination of the list.
- Users, authentication or per-user task lists.
- Fields beyond title and due date (description, priority, status, times of day, time zones).

## Assumptions

- **A1** The resource path is `/tasks` with fields `id`, `title`, `due_date`, all in JSON (other option: a versioned prefix such as `/v1/tasks`; affects AC-001.1 to AC-001.7).
- **A2** `id` is an opaque, server-assigned unique string, such as a UUID (other option: an increasing integer starting at 1; affects AC-001.1, AC-001.5).
- **A3** A title is 1 to 200 characters after trimming leading and trailing whitespace; whitespace-only is rejected (other option: no upper limit or a different limit; affects AC-001.3).
- **A4** The title is returned exactly as sent (other option: returned trimmed; affects AC-001.1).
- **A5** `due_date` is a date without time in `YYYY-MM-DD`; a missing or `null` value means no due date; dates in the past are accepted (other option: a full timestamp, or rejecting past dates; affects AC-001.2, AC-001.4).
- **A6** Invalid input answers 422 with the framework's standard validation error body (other option: 400 with a custom error body; affects AC-001.3, AC-001.4).
- **A7** The list returns every task, oldest first, with no limit, because tasks live in memory only (other option: newest first, or a cap; affects AC-001.5).
- **A8** Unknown fields in the request body are ignored (other option: rejected with 422; affects AC-001.1).
- **A9** Each running instance keeps its own tasks; the feature assumes one instance, since in-memory data is not shared between replicas (other option: shared storage, out of scope here; affects AC-001.5, AC-001.7).

## Open questions

none

## Changelog

- 2026-11-14 created
