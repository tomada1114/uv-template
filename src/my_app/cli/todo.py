"""The ``my-app todo`` commands: thin wrappers around ``TodoService``."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated

import typer

from my_app.composition import build_container
from my_app.core.errors import AppError
from my_app.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator

    from my_app.composition import Container
    from my_app.core.models import Todo

# 2 stays Typer's own code for a usage error, so a domain failure is told apart.
EXIT_DOMAIN_ERROR = 1
COMPLETED_MARK = "x"
OPEN_MARK = " "

app = typer.Typer(
    help="Create, list, complete, and delete to-dos.", no_args_is_help=True
)


@app.callback()
def load_services(ctx: typer.Context) -> None:
    """Build the services once, unless the caller already supplied them.

    A caller passing ``obj=`` (tests, through ``CliRunner.invoke``) keeps one
    container across invocations; a real run builds it from the environment.
    """
    if ctx.obj is None:
        ctx.obj = build_container(Settings())


@app.command("add")
def add_todo(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="What needs doing.")],
) -> None:
    """Add a to-do."""
    with _exit_on_domain_error():
        todo = _container(ctx).todos.create(title)
    typer.echo(f"Added {_describe(todo)}")


@app.command("list")
def list_todos(ctx: typer.Context) -> None:
    """List every to-do, oldest first."""
    todos = _container(ctx).todos.list_todos()
    if not todos:
        typer.echo("No to-dos yet.")
    for todo in todos:
        typer.echo(_describe(todo))


@app.command("complete")
def complete_todo(
    ctx: typer.Context,
    todo_id: Annotated[int, typer.Argument(metavar="ID", help="The to-do's id.")],
) -> None:
    """Mark a to-do as completed."""
    with _exit_on_domain_error():
        todo = _container(ctx).todos.complete(todo_id)
    typer.echo(f"Completed {_describe(todo)}")


@app.command("delete")
def delete_todo(
    ctx: typer.Context,
    todo_id: Annotated[int, typer.Argument(metavar="ID", help="The to-do's id.")],
) -> None:
    """Delete a to-do."""
    with _exit_on_domain_error():
        _container(ctx).todos.delete(todo_id)
    typer.echo(f"Deleted to-do {todo_id}")


def _container(ctx: typer.Context) -> Container:
    """Return the container ``load_services`` put on the context."""
    container: Container = ctx.obj
    return container


@contextmanager
def _exit_on_domain_error() -> Iterator[None]:
    """Turn an expected domain error into a message on stderr and exit code 1.

    Only ``AppError`` is caught: anything else is a bug and keeps its
    traceback.

    Raises:
        typer.Exit: With ``EXIT_DOMAIN_ERROR`` when the block raised an
            ``AppError``.
    """
    try:
        yield
    except AppError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=EXIT_DOMAIN_ERROR) from error


def _describe(todo: Todo) -> str:
    """Render one to-do as a single line, e.g. ``3 [x] buy milk``."""
    mark = COMPLETED_MARK if todo.is_completed else OPEN_MARK
    return f"{todo.id} [{mark}] {todo.title}"
