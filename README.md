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
uv sync --all-groups --locked
# Optional but recommended when working in a Git checkout
uv run --locked pre-commit install --install-hooks
just check
```

`just install` installs pre-commit hooks automatically when the project lives in
a Git repository and skips that step for "Use this template" bootstrap copies
before Git is initialized.

## License

[MIT](https://github.com/your-username/uv-template/blob/main/LICENSE)
