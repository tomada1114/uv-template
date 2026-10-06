from __future__ import annotations

import pytest

from my_app.core.errors import AppError, InvalidTodoError, TodoNotFoundError


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TodoNotFoundError(7), id="not-found"),
        pytest.param(InvalidTodoError("bad title"), id="invalid"),
    ],
)
def test_domain_error_is_an_app_error(error):
    assert isinstance(error, AppError)


def test_todo_not_found_error_keeps_the_missing_id_and_names_it():
    error = TodoNotFoundError(42)

    assert error.todo_id == 42
    assert str(error) == "To-do 42 not found"
