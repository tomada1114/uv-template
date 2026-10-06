---
name: writing-python
description: >
  Covers how one module, class, or function is written in any layer of src/my_app/ or
  in scripts/: mypy strict and a commented Any, TYPE_CHECKING imports and the
  annotations Pydantic, FastAPI, and Typer read at run time, frozen dataclass versus
  Pydantic versus TypedDict versus Protocol, enums and named constants, Google
  docstrings, EAFP, context managers, match, logging, and a justified noqa. Use when
  writing or reviewing Python code, or fixing a ruff TC, D, EM, PLR2004, S, or A
  finding or a mypy error.
---

# Writing Python

**Owns:** how one module, class, or function is written, in any layer of `src/my_app/`
and in `scripts/`. **Does not own:** which layer code belongs in, and the shape of
models, ports, services, and adapters (`designing-core-logic`); the `AppError`
hierarchy and how an entry point reports it (`designing-errors`); a route
(`building-api-routes`); a command (`designing-clis`); how a test is written
(`tests/AGENTS.md` and AGENTS.md's "Conventions: tests/**/*.py").

## What the gates already decide

- Enforced by: `pyproject.toml` `[tool.mypy]` `strict = true` with
  `warn_unused_ignores` and `enable_error_code = ["ignore-without-code", ...]`. A
  `# type: ignore` needs its error code and a reason, or it fails.
- Enforced by: `[tool.ruff.lint.isort]` `required-imports` — every module opens with
  `from __future__ import annotations`.
- Enforced by: ruff `D` with `convention = "google"` — every public module, class, and
  function has a docstring (`tests/**` and `scripts/**` waive the missing-docstring
  rules, `D1`).
- Enforced by: ruff `PLR2004` (a bare literal in a comparison), `EM` (a string literal
  inside `raise X(...)`), `DTZ` (a naive `datetime`), `T20` (`print`), `A` (shadowing a
  builtin), `S` (bandit).

A `noqa`, `type: ignore`, or per-file ignore carries its reason on the same line, never
a bare code. `cli/serve.py` shows the shape:

```python
import uvicorn  # noqa: PLC0415 - keeps `my-app todo` from importing uvicorn
```

## Imports a framework reads at run time stay real

With postponed annotations, a name used only in an annotation belongs under
`if TYPE_CHECKING:`, and ruff's `TC` rules move it there. Pydantic models, FastAPI
routes, and Typer commands read their annotations at run time, so the types they name
must stay real imports. `pyproject.toml`'s `[tool.ruff.lint.flake8-type-checking]`
lists those base classes and decorators so ruff leaves them alone; a new framework hook
that reads annotations is added to that list, never silenced with a `noqa`.

`api/schemas.py` has both kinds in one file: `datetime` is a real import because a
`BaseModel` field names it, while `Todo` appears only in a method signature.

```python
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from my_app.core.models import Todo
```

## Choosing a type for a value

- **An internal value:** `@dataclass(frozen=True, slots=True)`. A change is a new value
  built with `dataclasses.replace`, never an in-place edit. `Todo`, `TodoDraft`, and
  `composition.Container` are all this shape.
- **Pydantic `BaseModel`:** only at a serialization boundary — the wire format in
  `api/schemas.py` and the environment in `settings.py` (`BaseSettings`). Never in
  `core/`, where `tests/core/test_imports.py` rejects any third-party import.
- **`Protocol`, not an ABC,** for an interface: `Clock` and `TodoRepository` in
  `core/ports.py`. Add `@runtime_checkable` only when a test must `isinstance` against
  it.
- **`TypedDict`** for a dict whose keys are fixed, such as a JSON shape you do not own.
  No module needs one yet.
- **`enum.Enum`** for a closed set instead of loose string constants; `IntEnum` when the
  members are also used as numbers, as `cli.errors.ExitCode` is by `typer.Exit`. Inside
  a Pydantic model, a `Literal` field does the same job on the wire:
  `HealthResponse.status: Literal["ok"]`.
- **`Any`** only with a comment saying why nothing narrower fits. `api/routers/todos.py`:
  ``# Any: FastAPI's own type for `responses=` values is dict[str, Any].``

## Names and constants

- Every literal that carries meaning is an `UPPER_SNAKE_CASE` module constant
  (`MAX_TITLE_LENGTH`, `DEFAULT_PORT`, `ENV_PREFIX`, `SQLITE_MAX_INTEGER`), kept in the
  module that owns the meaning; another module imports it rather than repeating the
  value, as `cli/errors.py` imports `ENV_PREFIX` from `settings.py`.
- A boolean is named `is_`, `has_`, `can_`, or `should_` (`Todo.is_completed`). A wire
  format may spell it differently; the schema owns that mapping (`TodoResponse.completed`).
- A private helper is `_name`, an internal module `_name.py`; `__name` only to avoid a
  clash in a subclass hierarchy.
- A function never shadows a builtin. A command or route whose natural name is a builtin
  gets a descriptive function name and its public name separately:
  `@app.command("list")` over `def list_todos(...)`.

## Functions, modules, and docstrings

- A 300-line module or a 40-line function is a review trigger, not a rule: split it only
  along a real responsibility boundary. One logical concern per module.
- Prefer three or fewer parameters; group related ones in a frozen dataclass or a
  `TypedDict`. An optional collaborator or a flag goes keyword-only after `*`, as in
  `create_app(settings=None, *, container=None)`.
- A Google-style docstring says why, not what the signature already says: `Args:`,
  `Returns:`, and `Raises:` each earn their line by stating a decision or a contract.
  "A factory rather than a module-level `app` so each test gets a fresh store" is the
  kind of sentence that belongs there.
- A Typer command's or a FastAPI route's docstring is one plain-text line, because it is
  published as `--help` or OpenAPI text. Its reasoning goes in a comment or the module
  docstring.

## Idioms

- **EAFP** for lookups and I/O: try the operation and translate the specific exception,
  rather than checking first. `adapters/memory.py` does it for a missing key:

  ```python
  try:
      return self._todos[todo_id]
  except KeyError:
      raise TodoNotFoundError(todo_id) from None
  ```

  `from None` drops a cause that adds nothing; `from error` keeps one that does, as
  `cli/errors.py` does when it turns an `AppError` into `typer.Exit`.
- **A context manager for every resource.** When an object's own `with` does not
  release it, compose `contextlib.closing`: `SqliteTodoRepository._transaction` closes
  the connection that `sqlite3.Connection`'s context manager only commits. A reusable
  boundary is a `@contextmanager` function (`cli.errors.exit_on_domain_error`).
- **`match`/`case`** for dispatch on type or shape (`_status_for` in `api/app.py`).
- **The walrus operator** where it removes a repeated expression:
  `if (path := settings.sqlite_path) is not None:` in `composition.py`.
- **Comprehensions** over `map()` and `filter()`; `*args`/`**kwargs` only when a call
  genuinely forwards them.
- **A raised message is built first** (`msg = f"..."`, then `raise InvalidTodoError(msg)`),
  which is what ruff's `EM` rules ask for.
- **Time is never read directly** in the core: it arrives through the injected `Clock`
  (`designing-core-logic`). Elsewhere, a `datetime` is always timezone-aware
  (`datetime.now(tz=UTC)`, as `composition.utc_now` does).

## Errors and logging

- Catch the most specific exception that can happen, and either handle it meaningfully
  or re-raise it; never swallow one silently, and never use an exception for ordinary
  control flow. Return `None` only when the caller expects absence.
- No module under `src/my_app/` logs yet; uvicorn's own log is the only one. When one
  does, it uses a module-level `logging.getLogger(__name__)` and calls
  `logger.exception(...)` inside the `except` block of an unexpected error, which keeps
  the traceback — never `logger.error(str(error))`.
- An expected `AppError` is reported by the entry point and not logged at all;
  **REQUIRED:** `designing-errors` for that boundary.

## Security

- A path built from outside input is resolved with `Path.resolve()` and checked to stay
  under its allowed root before it is opened.
- SQL uses `?` parameters only, with the statement a module constant spelled out in
  full; `adapters/sqlite.py`'s `_SELECT_ONE` and siblings show the shape, and ruff's
  `S608` flags SQL built from strings.
- A subprocess takes a fixed argv list, never `shell=True`; its `# noqa: S603` names why
  the argv is safe (`tests/cli/test_serve.py`).
- Ruff's bandit rules (`S`) stay on; a `noqa` for one argues that specific check.

## Performance

Do not optimize preemptively. Profile a measured hotspot first, and put the measurement
in the pull request description.
