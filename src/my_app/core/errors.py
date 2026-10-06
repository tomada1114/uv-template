"""Domain errors, each a subclass of one package base exception.

Entry points translate these into their own vocabulary (an HTTP status, an
exit code), so the core never needs to know which one called it.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for every error the application raises on purpose.

    Catching it separates an expected domain failure, which an entry point
    reports to its user, from a bug, which should surface as a traceback.
    """


class TodoNotFoundError(AppError):
    """Raised when no to-do has the requested id."""

    def __init__(self, todo_id: int) -> None:
        """Keep the missing id so callers can report it without parsing text.

        Args:
            todo_id: The id that matched no stored to-do.
        """
        super().__init__(f"To-do {todo_id} not found")
        self.todo_id = todo_id


class InvalidTodoError(AppError):
    """Raised when input would create a to-do that breaks a domain rule."""
