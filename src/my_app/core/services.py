"""Use cases: the operations every entry point offers on to-dos."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from my_app.core.models import TodoDraft, normalize_title

if TYPE_CHECKING:
    from my_app.core.models import Todo
    from my_app.core.ports import Clock, TodoRepository


class TodoService:
    """Create, list, complete, and delete to-dos.

    The API and the CLI both call this class and nothing below it, so a rule
    added here holds for every entry point.
    """

    def __init__(self, repository: TodoRepository, clock: Clock) -> None:
        """Bind the service to its storage and its source of time.

        Args:
            repository: Where to-dos are stored.
            clock: Stamps ``created_at``; injected so tests can fix the time.
        """
        self._repository = repository
        self._clock = clock

    def create(self, raw_title: str) -> Todo:
        """Validate a title and store a new, open to-do.

        Raises:
            InvalidTodoError: If the title breaks the length rule.
        """
        draft = TodoDraft(title=normalize_title(raw_title), created_at=self._clock())
        return self._repository.add(draft)

    def list_todos(self) -> list[Todo]:
        """Return every to-do, oldest first."""
        return self._repository.list_all()

    def complete(self, todo_id: int) -> Todo:
        """Mark a to-do as completed; completing it again changes nothing.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        todo = self._repository.get(todo_id)
        if todo.is_completed:
            return todo
        return self._repository.update(replace(todo, is_completed=True))

    def delete(self, todo_id: int) -> None:
        """Remove a to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        self._repository.delete(todo_id)
