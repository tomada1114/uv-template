from __future__ import annotations

from datetime import datetime
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from my_app.api.app import create_app
from my_app.core.models import MAX_TITLE_LENGTH
from my_app.settings import Settings


@pytest.fixture
def client():
    with TestClient(create_app(Settings(database_url=None))) as test_client:
        yield test_client


@pytest.fixture
def make_todo(client):
    """Create a to-do through the API and return its JSON body."""

    def _make(title: str = "buy milk") -> dict[str, object]:
        response = client.post("/todos", json={"title": title})
        assert response.status_code == HTTPStatus.CREATED
        body: dict[str, object] = response.json()
        return body

    return _make


def test_list_todos_empty_store_returns_empty_list(client):
    response = client.get("/todos")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == []


def test_create_todo_valid_title_returns_201_with_open_todo(client):
    response = client.post("/todos", json={"title": "  buy milk "})

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert body["title"] == "buy milk"
    assert body["completed"] is False
    assert isinstance(body["id"], int)
    assert datetime.fromisoformat(body["created_at"]).utcoffset() is not None


@pytest.mark.parametrize(
    "title",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace-only"),
        pytest.param("x" * (MAX_TITLE_LENGTH + 1), id="too-long"),
    ],
)
def test_create_todo_invalid_title_returns_422_and_stores_nothing(client, title):
    response = client.post("/todos", json={"title": title})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert "characters" in response.json()["detail"]
    assert client.get("/todos").json() == []


def test_create_todo_missing_title_returns_422(client):
    response = client.post("/todos", json={})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT


def test_list_todos_after_creates_returns_them_oldest_first(client, make_todo):
    first = make_todo("first")
    second = make_todo("second")

    response = client.get("/todos")

    assert response.json() == [first, second]


def test_complete_todo_existing_id_returns_completed_todo(client, make_todo):
    todo = make_todo()

    response = client.post(f"/todos/{todo['id']}/complete")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {**todo, "completed": True}


def test_complete_todo_unknown_id_returns_404(client):
    response = client.post("/todos/999/complete")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "To-do 999 not found"}


def test_delete_todo_existing_id_returns_204_and_removes_it(client, make_todo):
    todo = make_todo()

    response = client.delete(f"/todos/{todo['id']}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert response.content == b""
    assert client.get("/todos").json() == []


def test_delete_todo_unknown_id_returns_404(client):
    response = client.delete("/todos/999")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {"detail": "To-do 999 not found"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("POST", "/todos/abc/complete", id="complete"),
        pytest.param("DELETE", "/todos/abc", id="delete"),
    ],
)
def test_todo_route_non_integer_id_returns_422(client, method, path):
    response = client.request(method, path)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
