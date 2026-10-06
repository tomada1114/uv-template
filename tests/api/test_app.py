from __future__ import annotations

from http import HTTPStatus
from importlib.metadata import version

from fastapi.testclient import TestClient

from my_app.api.app import create_app
from my_app.core.errors import AppError
from my_app.settings import Settings

UNMAPPED_MESSAGE = "a rule with no status of its own"


class _UnmappedError(AppError):
    """A domain error ``create_app`` has no specific status for."""

    def __init__(self) -> None:
        super().__init__(UNMAPPED_MESSAGE)


def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_openapi_reports_the_installed_version(client):
    response = client.get("/openapi.json")

    assert response.json()["info"]["version"] == version("my-app")


def test_unmapped_app_error_returns_400_not_500(make_container):
    app = create_app(container=make_container())

    @app.get("/unmapped")
    def _raise_unmapped() -> None:
        raise _UnmappedError

    with TestClient(app) as client:
        response = client.get("/unmapped")

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json() == {"detail": UNMAPPED_MESSAGE}


def test_create_app_without_settings_reads_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("MY_APP_DATABASE_URL", f"sqlite:///{tmp_path / 'env.db'}")

    with TestClient(create_app()) as writer:
        created = writer.post("/todos", json={"title": "from env"})
    with TestClient(create_app()) as reader:
        titles = [todo["title"] for todo in reader.get("/todos").json()]

    assert created.status_code == HTTPStatus.CREATED
    assert titles == ["from env"]


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
