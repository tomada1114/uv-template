"""The interfaces the core needs from the outside world.

They are ``Protocol`` classes so an adapter satisfies one by shape alone: it
never imports or subclasses anything from the core to plug in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from my_app.core.models import Todo, TodoDraft


class Clock(Protocol):
    """Return the current time as a timezone-aware UTC ``datetime``.

    Injected rather than read from ``datetime.now`` so tests can fix the time.
    """

    def __call__(self) -> datetime:
        """Return the current UTC time."""


@runtime_checkable
class TodoRepository(Protocol):
    """Stores to-dos and assigns their ids.

    Every implementation must pass the shared contract suite in
    ``tests/adapters/test_repository_contract.py``. Runtime-checkable so that
    suite can also assert an adapter has every method, not only mypy.
    """

    def add(self, draft: TodoDraft) -> Todo:
        """Store a draft and return it with its newly assigned id."""

    def get(self, todo_id: int) -> Todo:
        """Return the to-do with this id.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """

    def list_all(self) -> list[Todo]:
        """Return every stored to-do in ascending id order."""

    def update(self, todo: Todo) -> Todo:
        """Replace the stored to-do that has ``todo.id`` and return it.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """

    def delete(self, todo_id: int) -> None:
        """Remove the to-do with this id.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
