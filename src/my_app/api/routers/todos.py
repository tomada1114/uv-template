"""The to-do routes: thin HTTP wrappers around ``TodoService``.

Domain errors are left to propagate; the handlers ``create_app`` registers
turn them into 404 and 422 responses in one place.
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter

from my_app.api.dependencies import TodoServiceDep
from my_app.api.schemas import TodoCreateRequest, TodoResponse

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("")
def list_todos(service: TodoServiceDep) -> list[TodoResponse]:
    """List every to-do, oldest first; an empty store returns ``[]``."""
    return [TodoResponse.from_domain(todo) for todo in service.list_todos()]


@router.post("", status_code=HTTPStatus.CREATED)
def create_todo(body: TodoCreateRequest, service: TodoServiceDep) -> TodoResponse:
    """Create a to-do from a title."""
    return TodoResponse.from_domain(service.create(body.title))


@router.post("/{todo_id}/complete")
def complete_todo(todo_id: int, service: TodoServiceDep) -> TodoResponse:
    """Mark a to-do as completed."""
    return TodoResponse.from_domain(service.complete(todo_id))


@router.delete("/{todo_id}", status_code=HTTPStatus.NO_CONTENT)
def delete_todo(todo_id: int, service: TodoServiceDep) -> None:
    """Delete a to-do."""
    service.delete(todo_id)
