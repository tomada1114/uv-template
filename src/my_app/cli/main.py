"""The ``my-app`` root command: the ``todo`` group and ``serve``."""

from __future__ import annotations

from typing import Annotated

import typer
import uvicorn

from my_app.api.app import create_app
from my_app.cli import todo
from my_app.settings import Settings

# Loopback by default: exposing the server beyond this machine is an explicit
# `--host 0.0.0.0`, never an accident.
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000

app = typer.Typer(help="Manage to-dos and serve the HTTP API.", no_args_is_help=True)
app.add_typer(todo.app, name="todo")


@app.command()
def serve(
    host: Annotated[str, typer.Option(help="Interface to bind.")] = DEFAULT_HOST,
    port: Annotated[int, typer.Option(help="Port to listen on.")] = DEFAULT_PORT,
) -> None:
    """Serve the HTTP API with uvicorn until interrupted.

    For auto-reload while developing, use ``just dev`` instead.
    """
    uvicorn.run(create_app(Settings()), host=host, port=port)
