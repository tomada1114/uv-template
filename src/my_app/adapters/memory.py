"""A process-local to-do repository, the default store and the tests' fake."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from my_app.core.errors import TodoNotFoundError
from my_app.core.models import Todo

if TYPE_CHECKING:
    from my_app.core.models import TodoDraft


class InMemoryTodoRepository:
    """Keep to-dos in a dict for the life of the process.

    FastAPI runs synchronous endpoints in a thread pool, so every access takes
    a lock: two concurrent creates must never receive the same id.
    """

    def __init__(self) -> None:
        """Start empty, with ids counting up from 1."""
        self._todos: dict[int, Todo] = {}
        self._last_id = 0
        self._lock = threading.Lock()

    def add(self, draft: TodoDraft) -> Todo:
        """Store a draft under the next id."""
        with self._lock:
            self._last_id += 1
            todo = Todo(
                id=self._last_id, title=draft.title, created_at=draft.created_at
            )
            self._todos[todo.id] = todo
            return todo

    def get(self, todo_id: int) -> Todo:
        """Return a stored to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        with self._lock:
            try:
                return self._todos[todo_id]
            except KeyError:
                raise TodoNotFoundError(todo_id) from None

    def list_all(self) -> list[Todo]:
        """Return every to-do in ascending id order."""
        with self._lock:
            return [self._todos[todo_id] for todo_id in sorted(self._todos)]

    def update(self, todo: Todo) -> Todo:
        """Replace a stored to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        with self._lock:
            if todo.id not in self._todos:
                raise TodoNotFoundError(todo.id)
            self._todos[todo.id] = todo
            return todo

    def delete(self, todo_id: int) -> None:
        """Remove a stored to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        with self._lock:
            try:
                del self._todos[todo_id]
            except KeyError:
                raise TodoNotFoundError(todo_id) from None
