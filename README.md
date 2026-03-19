# my-package

[![CI](https://github.com/your-username/my-package/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/my-package/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/your-username/my-package/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/my-package)
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

## Design Philosophy

Every choice in this template has a reason. If you disagree with a decision,
you know exactly what to change and why it was there in the first place.

### Why `src/` layout?

The `src/` layout prevents accidental imports of the local package during
development and testing. It ensures that tests always run against the
*installed* version, catching packaging errors before they reach users.

### Why strict mypy + comprehensive Ruff rules?

Type errors and lint issues are cheapest to fix at write time. Strict settings
from day one mean every line of code is held to the same standard — there is
never a "legacy" codebase to clean up. LLMs generating code also benefit from
strict rules: they produce higher-quality output when constraints are clear.

### Why zero runtime dependencies?

A library template should not impose opinions about logging, HTTP clients, or
data validation. You add what you need. Starting from zero keeps the dependency
tree small and avoids conflicts with downstream users.

### Why Just over Make?

Just has cleaner syntax (no mandatory tabs), better cross-platform support, and
more readable recipe definitions. It is a task runner, not a build system —
which is exactly what a Python project needs.

### Why CLAUDE.md?

AI-assisted development is the norm, not the exception. `CLAUDE.md` gives LLMs
the context they need to generate code that matches your project's standards,
architecture, and conventions — reducing review cycles.

### Why 80% coverage minimum?

80% is high enough to catch most regressions but low enough to avoid
test-for-the-sake-of-testing. Branch coverage is enabled, so conditional logic
is meaningfully tested.

## Using This Template

1. Click **"Use this template"** on GitHub (or clone and remove `.git`)
2. Replace all occurrences of `my-package` and `my_package` with your project name
3. Update `pyproject.toml` metadata (author, description, URLs)
4. Update `README.md`, `SECURITY.md`, and `CLAUDE.md`
5. Replace the placeholder implementation and keep `src/my_package/__init__.py`,
   `docs/reference.md`, and the usage examples in sync with your public API

Search for `your-username` and `my-package` to find all placeholders:

```bash
rg -n "your-username|my-package|my_package|Your Name|you@example" .
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for full setup instructions.

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

- [Getting Started](https://your-username.github.io/my-package/getting-started/)
- [API Reference](https://your-username.github.io/my-package/reference/)

## License

[MIT](LICENSE)
