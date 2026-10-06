"""A to-do repository backed by a SQLite file, using only the stdlib driver."""

from __future__ import annotations

import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime
from typing import TYPE_CHECKING

from my_app.core.errors import TodoNotFoundError
from my_app.core.models import Todo

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from my_app.core.models import TodoDraft

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    is_completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
)
"""
# Spelled out in full rather than assembled, so no query string is ever built
# at run time; _to_todo relies on this column order.
_SELECT_ONE = "SELECT id, title, is_completed, created_at FROM todos WHERE id = ?"
_SELECT_ALL = "SELECT id, title, is_completed, created_at FROM todos ORDER BY id"
_INSERT = "INSERT INTO todos (title, created_at) VALUES (?, ?) RETURNING id"
_UPDATE = "UPDATE todos SET title = ?, is_completed = ?, created_at = ? WHERE id = ?"
_DELETE = "DELETE FROM todos WHERE id = ?"


class SqliteTodoRepository:
    """Store to-dos in one SQLite table.

    Each call opens and closes its own connection. That costs a little per
    call, but a connection is never shared across the threads FastAPI runs
    synchronous endpoints on, which ``sqlite3`` would otherwise refuse.
    """

    def __init__(self, path: Path) -> None:
        """Create the database file, its directory, and the table if missing.

        Args:
            path: The SQLite file; created on first use.
        """
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._transaction() as connection:
            connection.execute(_CREATE_TABLE)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection that commits on success, rolls back on error, then closes.

        ``sqlite3.Connection``'s own context manager only ends the transaction,
        so ``closing`` is what releases the file handle.
        """
        with closing(sqlite3.connect(self._path)) as connection, connection:
            yield connection

    def add(self, draft: TodoDraft) -> Todo:
        """Insert a draft and return it with the id SQLite assigned."""
        with self._transaction() as connection:
            (todo_id,) = connection.execute(
                _INSERT, (draft.title, draft.created_at.isoformat())
            ).fetchone()
        return Todo(id=todo_id, title=draft.title, created_at=draft.created_at)

    def get(self, todo_id: int) -> Todo:
        """Return a stored to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        with self._transaction() as connection:
            row = connection.execute(_SELECT_ONE, (todo_id,)).fetchone()
        if row is None:
            raise TodoNotFoundError(todo_id)
        return _to_todo(row)

    def list_all(self) -> list[Todo]:
        """Return every to-do in ascending id order."""
        with self._transaction() as connection:
            rows = connection.execute(_SELECT_ALL).fetchall()
        return [_to_todo(row) for row in rows]

    def update(self, todo: Todo) -> Todo:
        """Replace a stored to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        with self._transaction() as connection:
            cursor = connection.execute(
                _UPDATE,
                (todo.title, todo.is_completed, todo.created_at.isoformat(), todo.id),
            )
        if cursor.rowcount == 0:
            raise TodoNotFoundError(todo.id)
        return todo

    def delete(self, todo_id: int) -> None:
        """Remove a stored to-do.

        Raises:
            TodoNotFoundError: If no to-do has this id.
        """
        with self._transaction() as connection:
            cursor = connection.execute(_DELETE, (todo_id,))
        if cursor.rowcount == 0:
            raise TodoNotFoundError(todo_id)


def _to_todo(row: tuple[int, str, int, str]) -> Todo:
    """Rebuild a domain to-do from a row in the ``_SELECT_*`` column order."""
    todo_id, title, is_completed, created_at = row
    return Todo(
        id=todo_id,
        title=title,
        created_at=datetime.fromisoformat(created_at),
        is_completed=bool(is_completed),
    )
