# my-app

[![CI](https://github.com/your-username/uv-template/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/uv-template/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/your-username/uv-template/blob/main/LICENSE)

A short description of what this application does.

## Quickstart

```bash
uv sync --locked
export MY_APP_DATABASE_URL=sqlite:///todos.db  # keep to-dos between commands
uv run --locked my-app todo add "buy milk"     # Added 1 [ ] buy milk
uv run --locked my-app todo list               # 1 [ ] buy milk
uv run --locked my-app serve                   # HTTP API on http://127.0.0.1:8000 (Ctrl-C to stop)
```

With the server running, `curl http://127.0.0.1:8000/healthz` returns
`{"status":"ok"}`, and the interactive API docs are at
<http://127.0.0.1:8000/docs>.

| CLI | HTTP | Result |
|---|---|---|
| `my-app todo add TITLE` | `POST /todos` `{"title": "..."}` | 201 with the new to-do |
| `my-app todo list` | `GET /todos` | every to-do, oldest first (`[]` when empty) |
| `my-app todo complete ID` | `POST /todos/{id}/complete` | the completed to-do |
| `my-app todo delete ID` | `DELETE /todos/{id}` | 204 |

An unknown id is a 404 from the API and exit code 1 from the CLI; a title that
is empty or longer than 200 characters after trimming is a 422 and exit code 1.
Both print the reason (`detail` in the JSON body, stderr on the CLI).

## Configuration

Settings are read from environment variables prefixed with `MY_APP_`.

| Variable | Default | Effect |
|---|---|---|
| `MY_APP_DATABASE_URL` | unset | Unset keeps to-dos in memory, so they vanish when the process exits. `sqlite:///<path>` stores them in a SQLite file at `<path>`, created on first use. |

> [!NOTE]
> Each `my-app todo` invocation is its own process, so without
> `MY_APP_DATABASE_URL` the CLI forgets every to-do as soon as the command
> exits. The in-memory default suits the API server and tests; point the
> variable at a SQLite file for anything you want to keep.

## Architecture

```
src/my_app/
├── core/            # Domain model, ports (typing.Protocol), services, errors — no frameworks
├── adapters/        # In-memory and SQLite repositories implementing the core's ports
├── api/             # FastAPI app factory, routers, request/response models
├── cli/             # Typer commands
├── settings.py      # MY_APP_* environment variables
└── composition.py   # The one place adapters are wired into services
```

The API and the CLI are thin: both get their services from
`composition.build_container` and only translate between their own protocol
and the core. The core imports neither of them, nor any framework or driver;
lint (`ruff` `TID251`) and a test enforce that, so either entry point — or the
SQLite adapter — can be deleted without touching the core.

## Development

See [CONTRIBUTING.md](https://github.com/your-username/uv-template/blob/main/CONTRIBUTING.md)
for full setup instructions.

```bash
just install   # dependencies + git hooks, then checks the hooks are in place
just check
just dev        # API with auto-reload on http://127.0.0.1:8000
just run --help # the CLI, through uv
```

The git hooks are not optional: they carry the secret gate that refuses a
commit staging a secret, for every author. `just install` installs the
dependencies and the `pre-commit` and `pre-merge-commit` hooks, then fails if
either hook is missing. `ALLOW_MISSING_GIT_HOOKS=1 just install` still tries
to install them but only warns when that fails (`CI=true` does the same).
Outside a Git repository — a "Use this template" copy before `git init` — it
skips the hooks. Without Just, run `uv sync --all-groups --locked` and then
`uv run --locked pre-commit install --install-hooks`.

## License

[MIT](https://github.com/your-username/uv-template/blob/main/LICENSE)
