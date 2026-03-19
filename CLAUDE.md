# Project Guide

## Overview

This is a Python library built with [uv](https://docs.astral.sh/uv/) and
[hatchling](https://hatch.pypa.io/). It uses a strict `src/` layout with
comprehensive type checking and linting.

## Quick Reference

```bash
just install   # Install dependencies and git hooks when .git/ is present
just fmt       # Format code (ruff format + ruff check --fix)
just lint      # Lint (ruff check) + type check (mypy)
just test      # Run tests with coverage
just smoke     # Build and verify the wheel in a temp virtual environment
just check     # Run all checks: fmt → lint → test
just docs      # Serve docs locally
just build     # Build distribution packages
```

Without Just: replace `just <cmd>` with the corresponding `uv run` commands
in the `justfile`.

## Code Standards

- **Type hints required** on all public functions and methods
- **mypy strict mode** is enabled — no `Any` types without justification
- **Ruff** enforces a comprehensive rule set (see `pyproject.toml [tool.ruff.lint]`)
- **Line length**: 88 characters
- **Imports**: use `from __future__ import annotations` in every file
- **Style**: Google-style docstrings

## Architecture

```
src/my_package/
├── __init__.py   # Public API — export everything users need here
├── py.typed      # PEP 561 marker for typed package
└── core.py       # Placeholder module — replace and re-export via __init__.py
```

- Keep the public API surface small — export via `__init__.py.__all__`
- Internal modules can use a leading underscore (`_internal.py`)
- Separate concerns: one module per logical unit
- Update `docs/reference.md` and README examples whenever you change the public API

## Testing

- Framework: **pytest**
- Coverage threshold: **80%** (branch coverage enabled)
- Test files mirror source structure: `tests/test_<module>.py`
- Fixtures go in `tests/conftest.py`

## Post-Code Change Workflow

After making any code changes, ALWAYS run:

- `just fmt` — Format and auto-fix
- `just lint` — Lint + type check
- `just test` — Run tests with coverage

Or simply: `just check` (runs all three sequentially)

## Review Checklist

Before submitting a PR:

1. `just check` passes (format, lint, type check, tests)
2. New public APIs have type annotations and docstrings
3. Tests cover the new functionality
4. No unnecessary dependencies added

## Important Reminders

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files unless explicitly requested
- Dependencies should always be added to the appropriate group in pyproject.toml
