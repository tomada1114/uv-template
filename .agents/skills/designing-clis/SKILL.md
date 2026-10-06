---
name: designing-clis
description: >
  Covers the Typer entry point in src/my_app/cli/: the my-app root app in main.py, one
  Typer group per resource, the callback that puts the composition root's Container on
  ctx.obj, commands wrapped in exit_on_domain_error, stdout for results and stderr for
  errors, one-line command docstrings, the deferred FastAPI and uvicorn imports in
  serve.py, and CliRunner tests passing obj=. Use when adding or changing a command, an
  argument or option, or command output, or when removing the CLI. The skill is deleted
  along with src/my_app/cli/.
---

# Designing CLIs

**Owns:** everything under `src/my_app/cli/` and `tests/cli/` — the command tree, how a
command gets its services and settings, what it prints where, and how it is tested.
**Does not own:** the exit-code table and what maps to each code (`designing-errors`);
the service a command calls (`designing-core-logic`); running the installed `my-app`
by hand (`running-the-app`); module-level Python style (`writing-python`).

## A project without the CLI

This skill describes the command-line entry point only. A project that drops the CLI
deletes `.agents/skills/designing-clis/` with it, runs `just agents-sync`, and removes
the skill's row from AGENTS.md's Skills table, alongside the files and configuration
AGENTS.md's "Architecture" lists for that removal.

## The command tree

- `cli/main.py` holds the root `app = typer.Typer(help=..., no_args_is_help=True)`, the
  `my-app` console script (`[project.scripts]` in `pyproject.toml`). It registers each
  group with `app.add_typer(<module>.app, name=...)` and `serve` with
  `app.command()(serve)`, and holds nothing else.
- Each group is its own module with its own `typer.Typer(help=..., no_args_is_help=True)`,
  so `my-app <group>` with no subcommand prints help rather than doing something.
- A command whose natural name is a builtin is registered by name over a descriptive
  function: `@app.command("list")` on `def list_todos(...)`.

## Services come from the group's callback

The group's `@app.callback()` builds the container once per invocation and puts it on
`ctx.obj`; every command reads it from there through a typed helper. A caller that
already passed `obj=` — a test, through `CliRunner.invoke` — keeps its own container.
A command never calls `build_container` or constructs an adapter itself, and never
builds `Settings()` directly: `load_settings()` is what turns an invalid `MY_APP_*`
variable into exit 3 and one line instead of a traceback.

```python
@app.callback()
def load_services(ctx: typer.Context) -> None:
    """Create, list, complete, and delete to-dos."""
    if ctx.obj is None:
        ctx.obj = build_container(load_settings())
```

## A command's shape

- Parameters are `Annotated[T, typer.Argument(...)]` or `typer.Option(...)` with a
  `help=`, and a `metavar=` where the parameter name reads badly in usage text
  (`metavar="ID"`). A typed parameter (`int`) gives Typer's own usage error, exit 2,
  for a malformed value. Defaults are named module constants.
- The docstring is one plain-text line, because Typer prints it as `--help`. Reasoning
  goes in the module docstring or a comment.
- The service call that can raise an `AppError` sits inside
  `with exit_on_domain_error():`, and the output is printed after the block, so the
  wrapper maps only the domain failure. A command whose service cannot raise one (a
  listing) needs no wrapper.

```python
@app.command("complete")
def complete_todo(
    ctx: typer.Context,
    todo_id: Annotated[int, typer.Argument(metavar="ID", help="The to-do's id.")],
) -> None:
    """Mark a to-do as completed."""
    with exit_on_domain_error():
        todo = _container(ctx).todos.complete(todo_id)
    typer.echo(f"Completed {_describe(todo)}")
```

## Output, errors, and logging

- **Results go to stdout through `typer.echo`,** one line per item in a stable format a
  script can split, rendered by one helper (`_describe` prints `3 [x] buy milk`) with
  its markers as named constants. An empty result says so in words ("No to-dos yet.")
  rather than printing nothing. `print` fails lint (`T20`).
- **Failures go to stderr as one line,** and only through the two helpers in
  `cli/errors.py` — `exit_on_domain_error()` and `load_settings()` — so the `Error: `
  prefix and the exit code stay uniform. A command never echoes an error itself and
  never raises `typer.Exit` with a bare integer: it uses an `ExitCode` member. The
  codes are `designing-errors`'.
- **No logging and no progress chatter on stdout.** No module under `cli/` logs; a
  usage error's boxed message is Typer's own.

## Each invocation is its own process

A real run builds a fresh container, so with `MY_APP_DATABASE_URL` unset the in-memory
store forgets everything when the command exits; the README's Configuration note says
so to users. Tests reproduce one long-lived process by passing the same container as
`obj=` to every invocation.

## `serve` and imports

`cli/serve.py` is the CLI's only bridge to the API, a module of its own so that dropping
the API means deleting it and its registration line in `cli/main.py`. It imports
uvicorn and `create_app` inside the command, each with a `noqa: PLC0415` that says why,
so `my-app <group> ...` never loads the server stack;
`tests/cli/test_serve.py::test_cli_import_does_not_load_the_server_stack` proves it in
a fresh interpreter. No other CLI module imports `my_app.api`, and a future command
that needs a heavy optional stack defers its import the same way. `serve` binds
`127.0.0.1` unless `--host` says otherwise, and its default port is the developer's
(`running-the-app`).

## Adding a command

1. The service method it calls exists first, with its tests. **REQUIRED:**
   `designing-core-logic`.
2. The command goes in its group's module in the shape above; a new group is a new
   module with its own `app` and callback, registered in `cli/main.py`.
3. Test it (below): the happy path with exact stdout, each domain error with
   `ExitCode.DOMAIN_ERROR`, and a malformed argument with `ExitCode.USAGE_ERROR`.
4. Add it to the README's CLI/HTTP table.

## Testing a command

- Drive the app in-process with `typer.testing.CliRunner` and `obj=` a container from
  the `make_container` fixture, never by spawning `my-app`. `tests/cli/test_todo.py`'s
  `run` fixture wraps that, sharing one container across calls:

  ```python
  runner = CliRunner()
  container = make_container()

  def _run(*args: str) -> Result:
      return runner.invoke(app, list(args), obj=container)
  ```

- Assert `result.exit_code` against an `ExitCode` member, `result.stdout` exactly, and
  `result.stderr` for the error line; a failure also asserts `stdout == ""`.
- Only a test of reading settings omits `obj=`, and it sets `MY_APP_DATABASE_URL` to a
  `tmp_path` file with `monkeypatch`.
- `serve` is tested with `uvicorn.run` replaced by a recording fake (`serve_calls` in
  `tests/cli/test_serve.py`); a test never binds a port.
- Run `uv run --locked pytest tests/cli/`.
