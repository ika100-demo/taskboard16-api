"""HTTP routes for tasks."""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends

from .schemas import TaskCreate, TaskOut
from .store import Task, TaskStore, get_task_store

router = APIRouter(tags=["tasks"])
log = structlog.get_logger()
StoreDep = Annotated[TaskStore, Depends(get_task_store)]


@router.post("/tasks", status_code=201, response_model=TaskOut)
def create_task(payload: TaskCreate, store: StoreDep) -> Task:
    task = store.add(payload.title, payload.due_date)
    log.info("task_created", task_id=task.id)
    return task


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(store: StoreDep) -> list[Task]:
    return store.list()
