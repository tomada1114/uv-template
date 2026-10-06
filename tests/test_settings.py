from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from my_app.settings import Settings


def test_settings_database_url_unset_selects_in_memory_store():
    settings = Settings()

    assert settings.database_url is None
    assert settings.sqlite_path is None


@pytest.mark.parametrize(
    ("url", "expected_path"),
    [
        pytest.param("sqlite:///todos.db", Path("todos.db"), id="relative"),
        pytest.param(
            "sqlite:////var/lib/todos.db", Path("/var/lib/todos.db"), id="absolute"
        ),
    ],
)
def test_settings_database_url_from_env_selects_sqlite_path(
    monkeypatch, url, expected_path
):
    monkeypatch.setenv("MY_APP_DATABASE_URL", url)

    settings = Settings()

    assert settings.database_url == url
    assert settings.sqlite_path == expected_path


def test_settings_unprefixed_env_var_is_ignored(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///other.db")

    assert Settings().database_url is None


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("postgresql://localhost/todos", id="other-scheme"),
        pytest.param("sqlite:///", id="no-path"),
        pytest.param("", id="empty"),
    ],
)
def test_settings_unsupported_database_url_raises_validation_error(monkeypatch, url):
    monkeypatch.setenv("MY_APP_DATABASE_URL", url)

    with pytest.raises(
        ValidationError, match=r"database_url must look like 'sqlite:///<path>'"
    ):
        Settings()
