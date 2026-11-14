"""Request and response models for the tasks API."""

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, StrictStr, field_validator

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_TITLE = 200


class TaskCreate(BaseModel):
    title: StrictStr
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def _check_title(cls, v: str) -> str:
        if not 1 <= len(v.strip()) <= _MAX_TITLE:
            raise ValueError("title must be 1 to 200 characters after trimming")
        if "\x00" in v:
            raise ValueError("title must not contain the NUL character")
        return v

    @field_validator("due_date", mode="before")
    @classmethod
    def _check_due_date(cls, v: Any) -> date | None:
        if v is None:
            return None
        if isinstance(v, str) and _DATE_RE.match(v):
            return date.fromisoformat(v)
        raise ValueError("due_date must be a calendar date in the form YYYY-MM-DD")


class TaskOut(BaseModel):
    id: str
    title: str
    due_date: date | None
