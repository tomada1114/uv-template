"""The composition root: the one place adapters are wired into services.

Both entry points get their services from ``build_container`` and from
nowhere else, so swapping a repository is a change to this module only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from my_app.adapters.memory import InMemoryTodoRepository
from my_app.adapters.sqlite import SqliteTodoRepository
from my_app.core.services import TodoService

if TYPE_CHECKING:
    from my_app.core.ports import Clock, TodoRepository
    from my_app.settings import Settings


@dataclass(frozen=True, slots=True)
class Container:
    """The services an entry point may call, built once per process."""

    todos: TodoService


def utc_now() -> datetime:
    """Return the current time in UTC; the production ``Clock``."""
    return datetime.now(tz=UTC)


def build_container(settings: Settings, clock: Clock = utc_now) -> Container:
    """Choose the adapters ``settings`` asks for and wire them into services.

    Args:
        settings: Selects the repository through ``database_url``.
        clock: Stamps new to-dos; tests pass a fixed one.

    Returns:
        The services, ready for an entry point to call.
    """
    return Container(todos=TodoService(_build_repository(settings), clock))


def _build_repository(settings: Settings) -> TodoRepository:
    """Return the SQLite repository when a path is configured, else memory."""
    if (path := settings.sqlite_path) is not None:
        return SqliteTodoRepository(path)
    return InMemoryTodoRepository()
