"""The ``my-app todo`` commands: thin wrappers around ``TodoService``.

Command docstrings stay one line because Typer prints them as ``--help``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from my_app.cli.errors import exit_on_domain_error, load_settings
from my_app.composition import build_container

if TYPE_CHECKING:
    from my_app.composition import Container
    from my_app.core.models import Todo

COMPLETED_MARK = "x"
OPEN_MARK = " "

app = typer.Typer(
    help="Create, list, complete, and delete to-dos.", no_args_is_help=True
)


@app.callback()
def load_services(ctx: typer.Context) -> None:
    """Create, list, complete, and delete to-dos."""
    # A caller passing `obj=` (tests, through CliRunner.invoke) keeps one
    # container across invocations; a real run builds it from the environment.
    if ctx.obj is None:
        ctx.obj = build_container(load_settings())


@app.command("add")
def add_todo(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="What needs doing.")],
) -> None:
    """Add a to-do."""
    with exit_on_domain_error():
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
    with exit_on_domain_error():
        todo = _container(ctx).todos.complete(todo_id)
    typer.echo(f"Completed {_describe(todo)}")


@app.command("delete")
def delete_todo(
    ctx: typer.Context,
    todo_id: Annotated[int, typer.Argument(metavar="ID", help="The to-do's id.")],
) -> None:
    """Delete a to-do."""
    with exit_on_domain_error():
        _container(ctx).todos.delete(todo_id)
    typer.echo(f"Deleted to-do {todo_id}")


def _container(ctx: typer.Context) -> Container:
    """Return the container ``load_services`` put on the context."""
    container: Container = ctx.obj
    return container


def _describe(todo: Todo) -> str:
    """Render one to-do as a single line, e.g. ``3 [x] buy milk``."""
    mark = COMPLETED_MARK if todo.is_completed else OPEN_MARK
    return f"{todo.id} [{mark}] {todo.title}"
