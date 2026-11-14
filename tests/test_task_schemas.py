"""Unit tests for the task schemas."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from taskboard16_api.tasks.schemas import TaskCreate, TaskOut


@pytest.mark.parametrize(
    "title",
    [None, 123, "", "   ", "x" * 201, ["a"]],
)
def test_invalid_title_rejected(title: Any) -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title=title)


def test_missing_title_rejected() -> None:
    with pytest.raises(ValidationError):
        TaskCreate.model_validate({})


@pytest.mark.parametrize(
    "due",
    [
        "tomorrow",
        "2026-02-30",
        "2026-12-01T10:00:00Z",
        "2026-12-01T00:00:00",
        20261201,
        1764547200,
        "",
        True,
    ],
)
def test_invalid_due_date_rejected(due: Any) -> None:
    with pytest.raises(ValidationError):
        TaskCreate.model_validate({"title": "a", "due_date": due})


def test_valid_due_date() -> None:
    assert TaskCreate(title="a", due_date="2026-12-01").due_date == date(2026, 12, 1)  # type: ignore[arg-type]


def test_due_date_defaults_and_null() -> None:
    assert TaskCreate(title="a").due_date is None
    assert TaskCreate.model_validate({"title": "a", "due_date": None}).due_date is None


def test_title_preserved_with_spaces() -> None:
    assert TaskCreate(title="  Buy milk  ").title == "  Buy milk  "


def test_title_length_boundary() -> None:
    assert TaskCreate(title=" " + "x" * 200 + " ").title.strip() == "x" * 200
    with pytest.raises(ValidationError):
        TaskCreate(title=" " + "x" * 201 + " ")


def test_extra_fields_ignored() -> None:
    task = TaskCreate.model_validate({"title": "a", "id": "zzz", "foo": 1})
    assert not hasattr(task, "foo")


def test_task_out_serializes_date() -> None:
    out = TaskOut(id="1", title="a", due_date=date(2026, 12, 1))
    assert out.model_dump(mode="json") == {"id": "1", "title": "a", "due_date": "2026-12-01"}
    assert TaskOut(id="1", title="a", due_date=None).model_dump(mode="json")["due_date"] is None
