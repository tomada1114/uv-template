from __future__ import annotations

from datetime import UTC

from my_app.composition import utc_now
from my_app.settings import Settings


def test_build_container_default_settings_uses_an_independent_memory_store(
    make_container,
):
    first = make_container()
    second = make_container()

    first.todos.create("only in first")

    assert second.todos.list_todos() == []


def test_build_container_sqlite_settings_shares_the_file(make_container, tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'todos.db'}")
    created = make_container(settings).todos.create("buy milk")

    reopened = make_container(settings)

    assert reopened.todos.list_todos() == [created]


def test_build_container_injected_clock_stamps_created_at(make_container, fixed_now):
    todo = make_container().todos.create("buy milk")

    assert todo.created_at == fixed_now


def test_utc_now_returns_timezone_aware_utc_time():
    assert utc_now().tzinfo is UTC
