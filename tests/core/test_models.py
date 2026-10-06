from __future__ import annotations

import pytest

from my_app.core.errors import InvalidTodoError
from my_app.core.models import MAX_TITLE_LENGTH, normalize_title


@pytest.mark.parametrize(
    ("raw_title", "expected"),
    [
        pytest.param("buy milk", "buy milk", id="plain"),
        pytest.param("  buy milk\n", "buy milk", id="surrounding-whitespace"),
        pytest.param("x", "x", id="one-character"),
        pytest.param("x" * MAX_TITLE_LENGTH, "x" * MAX_TITLE_LENGTH, id="max-length"),
        pytest.param("牛乳を買う 🥛", "牛乳を買う 🥛", id="unicode"),
        pytest.param(
            f" {'x' * MAX_TITLE_LENGTH} ",
            "x" * MAX_TITLE_LENGTH,
            id="max-length-after-strip",
        ),
    ],
)
def test_normalize_title_valid_title_returns_stripped_title(raw_title, expected):
    assert normalize_title(raw_title) == expected


@pytest.mark.parametrize(
    ("raw_title", "length"),
    [
        pytest.param("", 0, id="empty"),
        pytest.param(" \t\n ", 0, id="whitespace-only"),
        pytest.param("x" * (MAX_TITLE_LENGTH + 1), MAX_TITLE_LENGTH + 1, id="too-long"),
    ],
)
def test_normalize_title_out_of_range_raises_invalid_todo_error(raw_title, length):
    with pytest.raises(InvalidTodoError, match=rf"1-200 characters .* got {length}$"):
        normalize_title(raw_title)
