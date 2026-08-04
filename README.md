# my-package

[![CI](https://github.com/your-username/my-package/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/my-package/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/my-package)](https://pypi.org/project/my-package/)
[![Python](https://img.shields.io/pypi/pyversions/my-package)](https://pypi.org/project/my-package/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A short description of what this library does.

## Quickstart

```bash
pip install my-package
# or
uv add my-package
```

```python
from my_package import add

result = add(1, 2)  # 3
```

## Development

See [CONTRIBUTING.md](https://github.com/your-username/my-package/blob/main/CONTRIBUTING.md)
for full setup instructions.

```bash
uv sync --all-groups
# Optional but recommended when working in a Git checkout
uv run pre-commit install --install-hooks
just check
```

`just install` installs pre-commit hooks automatically when the project lives in
a Git repository and skips that step for "Use this template" bootstrap copies
before Git is initialized.

For packaging verification, run `just smoke` (or `uv build && uv run python scripts/smoke_test.py`)
to install the freshly built wheel into a temporary virtual environment and
confirm the distribution imports from the wheel, not from `src/`.

## Documentation

- [API Reference](https://your-username.github.io/my-package/reference/)

## License

[MIT](LICENSE)
