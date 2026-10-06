from __future__ import annotations

from dataclasses import dataclass

import pytest
import uvicorn
from fastapi import FastAPI
from typer.testing import CliRunner

from my_app.cli.main import app


@dataclass
class _ServeCall:
    app: object
    host: str
    port: int


@pytest.fixture
def serve_calls(monkeypatch):
    """Record ``uvicorn.run`` calls instead of starting a real server.

    The server is the boundary: binding a port in a test would be slow, could
    collide with a developer's server, and would never return.
    """
    calls: list[_ServeCall] = []

    def _fake_run(served_app: object, *, host: str, port: int) -> None:
        calls.append(_ServeCall(served_app, host, port))

    monkeypatch.setattr(uvicorn, "run", _fake_run)
    return calls


def test_serve_without_options_binds_loopback_port_8000(serve_calls):
    result = CliRunner().invoke(app, ["serve"])

    assert result.exit_code == 0
    assert len(serve_calls) == 1
    assert (serve_calls[0].host, serve_calls[0].port) == ("127.0.0.1", 8000)
    assert isinstance(serve_calls[0].app, FastAPI)


def test_serve_with_options_binds_the_given_host_and_port(serve_calls):
    result = CliRunner().invoke(app, ["serve", "--host", "localhost", "--port", "9000"])

    assert result.exit_code == 0
    assert [(call.host, call.port) for call in serve_calls] == [("localhost", 9000)]


def test_serve_invalid_port_exits_with_usage_error_without_serving(serve_calls):
    result = CliRunner().invoke(app, ["serve", "--port", "not-a-port"])

    assert result.exit_code == 2
    assert serve_calls == []
