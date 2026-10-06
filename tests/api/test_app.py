from __future__ import annotations

from http import HTTPStatus
from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

from my_app.api.app import create_app
from my_app.settings import Settings


@pytest.fixture
def client():
    with TestClient(create_app(Settings(database_url=None))) as test_client:
        yield test_client


def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_openapi_reports_the_installed_version(client):
    response = client.get("/openapi.json")

    assert response.json()["info"]["version"] == version("my-app")


def test_create_app_without_settings_reads_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "env.db"
    monkeypatch.setenv("MY_APP_DATABASE_URL", f"sqlite:///{path}")

    with TestClient(create_app()) as client:
        client.post("/todos", json={"title": "from env"})

    assert path.is_file()


def test_create_app_each_call_owns_an_independent_store():
    with TestClient(create_app(Settings())) as first:
        first.post("/todos", json={"title": "only in first"})

    with TestClient(create_app(Settings())) as second:
        assert second.get("/todos").json() == []


def test_create_app_with_sqlite_keeps_todos_across_apps(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'todos.db'}")
    with TestClient(create_app(settings)) as first:
        first.post("/todos", json={"title": "survives"})

    with TestClient(create_app(settings)) as second:
        titles = [todo["title"] for todo in second.get("/todos").json()]

    assert titles == ["survives"]
