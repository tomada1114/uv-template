# my-package

[![CI](https://github.com/your-username/uv-template/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/uv-template/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/my-package)](https://pypi.org/project/my-package/)
[![Python](https://img.shields.io/pypi/pyversions/my-package)](https://pypi.org/project/my-package/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/your-username/uv-template/blob/main/LICENSE)

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

For packaging verification, run `just smoke` (or `uv build --clear && uv run
--locked python scripts/smoke_test.py`) to install the freshly built wheel and
source distribution into temporary virtual environments and confirm they import
from the artifacts, not from `src/`.

## Documentation

- [API Reference](https://your-username.github.io/uv-template/reference/)

## License

[MIT](https://github.com/your-username/uv-template/blob/main/LICENSE)
