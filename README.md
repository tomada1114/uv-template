# my-package

[![CI](https://github.com/your-username/uv-template/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/uv-template/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/your-username/uv-template/blob/main/LICENSE)

A short description of what this application does.

## Quickstart

```bash
uv sync --locked
uv run --locked python -c "from my_package import add; print(add(1, 2))"  # 3
```

## Development

See [CONTRIBUTING.md](https://github.com/your-username/uv-template/blob/main/CONTRIBUTING.md)
for full setup instructions.

```bash
just install   # dependencies + git hooks, then checks the hooks are in place
just check
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
