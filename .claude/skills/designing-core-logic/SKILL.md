---
name: designing-core-logic
description: >
  Covers what goes where beneath the entry points: models, rules, and services in
  src/my_app/core/, ports as typing.Protocol, the injected Clock, adapters in
  src/my_app/adapters/ and the shared repository contract suite, Settings in
  settings.py, and the composition root's build_container and Container. Use when
  adding a use case, a domain rule or model, a port, a repository or other adapter, or
  a MY_APP_ setting, or when ruff TID251 or tests/core/test_imports.py rejects an
  import in the core.
---

# Designing Core Logic

**Owns:** the layers beneath the entry points — what belongs in `core/`, how a port and
its adapters are shaped and tested, how configuration is read, and how
`composition.py` wires adapters into services. **Does not own:** the layer map and
removing an entry point (AGENTS.md's "Architecture"); the `AppError` hierarchy and its
mappings (`designing-errors`); exposing a service over HTTP (`building-api-routes`) or
as a command (`designing-clis`); module-level Python style (`writing-python`).

## The direction dependencies point

`api/` and `cli/` call services from `core/`, which they receive only from
`composition.build_container`; `adapters/` implement the ports `core/` declares; `core/`
imports nothing outside the standard library and itself.

- Enforced by: `pyproject.toml` `[tool.ruff.lint.flake8-tidy-imports.banned-api]`
  (`TID251`), which bans fastapi, typer, uvicorn, sqlite3, and httpx outside the layers
  re-allowed by its per-file-ignores.
- Enforced by: `tests/core/test_imports.py`, which is stricter: it rejects every
  third-party import in `core/` (Pydantic included) and any reach into another layer,
  across subpackages too.

A new framework or driver the core must not touch gets a `banned-api` entry and a
per-file-ignore for the one layer that uses it, in the same change that adds it.

## Models hold the invariants

A domain value is a frozen dataclass whose `__post_init__` refuses any state no rule
allows. The check runs on every construction — an adapter rebuilding a row,
`dataclasses.replace` producing a changed copy — so no code path can hold an invalid
value. A value that does not have its identity yet is its own type: `TodoDraft` has no
`id`, `Todo` has one, and both run `_check_invariants`.

A rule lives once, in the core, as a function both entry points reach through a
service. `normalize_title` strips and length-checks a title; the API's request model
and the CLI's argument leave the title as a plain `str`, so every entry point rejects
the same input with the same message.

## Services are the use cases

A service class groups the operations an entry point offers on one part of the domain.
Its constructor takes the ports and the clock it needs; its methods take what a user
supplies (`raw_title: str`, `todo_id: int`) and return domain models. Entry points call
a service and nothing below it, so a rule added to a service holds for every entry
point. A method's docstring records the behavior a caller may rely on — `complete`
returns an already-completed to-do unchanged, so a retried request is safe.

```python
def create(self, raw_title: str) -> Todo:
    draft = TodoDraft(title=normalize_title(raw_title), created_at=self._clock())
    return self._repository.add(draft)
```

Services are synchronous. FastAPI runs a synchronous route in its thread pool, so a
service and its adapters may be called from several threads at once; that is why
`InMemoryTodoRepository` takes a lock and `SqliteTodoRepository` opens a connection per
call.

## Ports describe what the core needs from outside

A port is a `typing.Protocol` in `core/ports.py`, typed with core models only. An
adapter satisfies it by shape and never imports or subclasses it. The port's docstrings
are the contract — what is returned, in what order, and what is raised — and
`TodoRepository` is `@runtime_checkable` so the contract suite can also assert that an
adapter has every method.

## Time and other outside inputs are injected

The core never calls `datetime.now()`, reads the environment, or opens a file. The
current time arrives through `Clock`, which any zero-argument callable returning a
timezone-aware `datetime` satisfies; a naive one is rejected by the model's invariant
check as a bug. Production passes `composition.utc_now`; tests pass the `fixed_clock`
fixture from `tests/conftest.py`, so a timestamp in an assertion is exact. Any other
outside input — randomness, an identifier generator, a remote call — gets a port of
the same kind rather than a direct call.

## Adapters implement a port

- An adapter in `adapters/` wraps one storage or I/O technology, holds no domain rule,
  and translates its driver's failures into the domain errors the port promises
  (`designing-errors`).
- It is safe to call from several threads; see "Services are the use cases".
- Its queries are module constants spelled out in full, never assembled at run time
  (`adapters/sqlite.py`).
- Every implementation of a port runs the one shared contract suite. A new repository
  joins `tests/adapters/test_repository_contract.py` by adding a `pytest.param` to
  `REPOSITORY_FACTORIES`; behavior only it has (the SQLite file outliving the object,
  the in-memory lock) goes in `tests/adapters/test_<adapter>.py`.
- The in-memory adapter doubles as the core's fake: `tests/core/test_services.py`
  builds a service over `InMemoryTodoRepository()` and `fixed_clock` instead of mocking
  the port.

## Settings are read once, at the boundary

`settings.py`'s `Settings` is the only place configuration enters, from
`MY_APP_`-prefixed environment variables (`ENV_PREFIX`). A new setting is a field on
`Settings`:

- validated in a `field_validator`, so a bad value fails at startup with a message that
  says what to set, rather than on the first request;
- turned into the form the composition root needs by a property (`sqlite_path` turns
  `database_url` into a `Path`), so adapters never parse configuration strings;
- deleted from the environment by `tests/conftest.py`'s autouse `_isolate_settings_env`
  fixture, so a developer's shell cannot leak into a test — add the new variable there;
- listed in the README's Configuration table.

## The composition root wires everything once

`composition.py` is the only module that constructs adapters and services.
`build_container(settings, clock=utc_now)` picks adapters from the settings
(`_build_repository`) and returns a frozen `Container` with one field per service; the
API stores it on `app.state` and the CLI on `ctx.obj`. A new service is a new
`Container` field built in `build_container`; a new adapter choice is a branch in the
function that picks it, driven by a setting.

```python
def build_container(settings: Settings, clock: Clock = utc_now) -> Container:
    return Container(todos=TodoService(_build_repository(settings), clock))
```

Tests build containers through the same function: the `make_container` fixture in
`tests/conftest.py` calls `build_container` with the fixed clock and in-memory storage
by default, and `tests/test_composition.py` covers the wiring itself.

## Adding a use case

1. A rule the operation needs goes in the model or a core function, with its
   `InvalidTodoError`-style domain error (`designing-errors`).
2. A method on the service, calling ports only, with `Args:`, `Returns:`, and `Raises:`.
3. A port method if storage must do something new, implemented in every adapter, and a
   contract-suite test that every adapter must pass.
4. Tests in `tests/core/` through the service's public methods, happy and error paths.
5. Expose it in each entry point that offers it. **REQUIRED:** `building-api-routes`
   for a route, `designing-clis` for a command.

Run the narrowest checks while iterating: `uv run --locked pytest tests/core/
tests/adapters/ tests/test_composition.py tests/test_settings.py`.
