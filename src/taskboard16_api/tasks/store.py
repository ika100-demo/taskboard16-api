"""Thread-safe in-memory task store."""

import threading
import uuid
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    due_date: date | None


class TaskStore:
    """Ordered in-memory list of tasks guarded by a lock."""

    def __init__(self) -> None:
        self._tasks: list[Task] = []
        self._lock = threading.Lock()

    def add(self, title: str, due_date: date | None) -> Task:
        task = Task(id=str(uuid.uuid4()), title=title, due_date=due_date)
        with self._lock:
            self._tasks.append(task)
        return task

    def list(self) -> list[Task]:
        with self._lock:
            return self._tasks.copy()


_store = TaskStore()


def get_task_store() -> TaskStore:
    return _store
