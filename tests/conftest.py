"""Fixtures shared by every layer's tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from my_app.composition import Container, build_container
from my_app.settings import ENV_PREFIX, Settings

FIXED_NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


def _fixed_clock() -> datetime:
    return FIXED_NOW


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch):
    """Keep a developer's own ``MY_APP_*`` variables out of every test.

    Without this, a shell exporting ``MY_APP_DATABASE_URL`` would point the
    tests at that database.
    """
    monkeypatch.delenv(f"{ENV_PREFIX}DATABASE_URL", raising=False)


@pytest.fixture
def fixed_now() -> datetime:
    """The instant ``fixed_clock`` always reads."""
    return FIXED_NOW


@pytest.fixture
def fixed_clock():
    """A ``Clock`` that always reads ``fixed_now``, so timestamps are exact."""
    return _fixed_clock


@pytest.fixture
def make_container():
    """Build a container through the composition root with a fixed clock.

    Defaults to the in-memory repository; pass ``Settings`` to choose another.
    """

    def _make(settings: Settings | None = None) -> Container:
        chosen = settings if settings is not None else Settings(database_url=None)
        return build_container(chosen, clock=_fixed_clock)

    return _make
