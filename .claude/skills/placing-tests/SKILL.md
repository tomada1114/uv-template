---
name: placing-tests
description: >
  Decides where a new test file goes under tests/ (tests/<layer>/test_<module>.py for
  src/my_app/<layer>/, tests/test_<module>.py for settings, composition, and scripts),
  where a fixture goes (tests/conftest.py, a layer conftest.py, or the test file), which
  command runs it, how pytest-split's .test_durations shards it in CI, and the 80%
  branch-coverage floor over src/. Use when adding a test file or a fixture, running one
  test, a coverage run drops below the floor, or CI shards grow unbalanced.
---

# Placing Tests

**Owns:** where a test file and a fixture go, which command runs them, how CI shards
them, and which coverage floor governs them. **Does not own:** how a test is written
(`writing-tests`); the tests bundled inside a skill's `scripts/tests/`
(`authoring-skills`); changing the floor, the pytest options, or the coverage config
(`changing-gates`).

## The tree mirrors the source

| Code under test | Its test file |
|---|---|
| `src/my_app/<layer>/<module>.py` (`core`, `adapters`, `api`, `cli`) | `tests/<layer>/test_<module>.py` |
| A top-level module (`settings.py`, `composition.py`) | `tests/test_<module>.py` |
| `scripts/<script>.py` | `tests/test_<script>.py` |
| Agent tier definitions in `.claude/agents/` and `.codex/agents/` | `tests/test_agent_tiers.py` |

- A new module gets its test file in the same commit as the module. **BACKGROUND:**
  `tdd`.
- Every directory under `tests/` carries an `__init__.py`; a new layer directory does
  too.
- `tests/core/test_errors.py` and `tests/cli/test_errors.py` share a basename on
  purpose: each mirrors its own `errors.py`.

Three files hold a rule for a whole layer rather than one module, and grow by a new case
rather than by a new file:

- `tests/adapters/test_repository_contract.py` — every repository adapter runs this one
  contract suite. A new adapter adds a `pytest.param`; only what one adapter alone does
  goes in `tests/adapters/test_<adapter>.py`. **REQUIRED:** `designing-core-logic`.
- `tests/core/test_imports.py` — the core's import boundary. **BACKGROUND:**
  `designing-core-logic`.
- `tests/core/test_errors.py` — every `AppError` subclass joins its parametrized tests.
  **REQUIRED:** `designing-errors`.

## Where a fixture goes

- Used by every layer: `tests/conftest.py`. It holds `make_container`, `fixed_clock`,
  `fixed_now`, and the autouse fixture that keeps a developer's `MY_APP_*` variables
  out of every test.
- Used by one layer: that layer's `conftest.py` — `tests/api/conftest.py` holds
  `client`.
- Used by one file: that file. A fixture moves up only when a second file needs it.
- The narrowest scope that works (`writing-tests`' "Fixtures").

## Running tests

```bash
uv run --locked pytest tests/<layer>/test_<module>.py::test_<name>   # one test
uv run --locked pytest tests/<layer>/                                  # one layer
just test                                                              # whole suite, coverage floor
```

`[tool.pytest.ini_options]` runs with `--import-mode=importlib`, `--strict-markers`,
and `--strict-config`: an unregistered marker or a misspelled option is an error, not a
warning. `just test` adds `-n auto`, so the suite runs across processes. The map from a
changed path to its narrowest check is AGENTS.md's "Validating a change".

## CI shards

CI's `test` job splits the suite into four shards with `pytest-split`, balanced by the
recorded run times in `.test_durations`. A test missing from that file is still run: it
is given the average recorded duration (observed in pytest-split 0.11.0's
`algorithms.py`, 2026-10-06). So a new test file needs no entry; regenerate the file with
`just test-durations` when the shards' run times drift apart, and commit it on its own.

## The coverage floor

- **80%, with branch coverage, over `src/` only.** `[tool.coverage.run]` sets
  `branch = true` and `source = ["src"]`; `just test` enforces the floor with
  `--cov-fail-under=80`, and CI's `Coverage` job with `coverage report --fail-under=80`
  after combining the shards. Neither `scripts/` nor `tests/` is measured, so a script's
  tests guard behavior but move no number.
- **A floor, not a ceiling.** It is never lowered, and no line leaves the measurement to
  move the number — AGENTS.md's "Security and human approval" holds that prohibition.
  `changing-gates` lists what counts as moving it.
- **Branch coverage matters more than line coverage.** Cover both sides of a
  conditional; a test that only adds a line hit is not the fix.
- **Missing coverage asks "is this reachable?"** If no input reaches the branch, delete
  it rather than test around it.
- **Never write a trivial test to hit the number.** Cover an edge case or an error path
  instead.

When `just test` fails on the floor, read the `term-missing` report it prints, add real
coverage for the uncovered branch, and run it again.
