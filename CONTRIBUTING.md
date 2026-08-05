# Contributing

Thank you for considering a contribution! This document explains how to set up
your development environment and submit changes.

## Prerequisites

Install these tools:

- [Python 3.12+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Just](https://just.systems/man/en/installation.html) (optional — you can run
  `uv run` commands directly)

Then:

```bash
uv sync --all-groups
```

If you're working in a Git checkout, also install the local hooks:

```bash
uv run pre-commit install --install-hooks
```

## Development Workflow

```bash
# Format and auto-fix
just fmt

# Lint + type check
just lint

# Run tests
just test

# Build and verify the wheel in an isolated temp environment
just smoke

# Run everything (format → lint → test)
just check
```

**Without Just**, run the equivalent commands:

```bash
uv run ruff check --fix .
uv run ruff format .
uv run ruff check .
uv run mypy src scripts tests
uv run pytest --cov --cov-report=term-missing:skip-covered --cov-fail-under=80
uv build && uv run python scripts/smoke_test.py
```

## Pull Request Process

1. Fork the repository and create a branch from `main`
2. Make your changes
3. Ensure `just check` passes
4. Write or update tests for your changes
5. Open a pull request using the PR template

### Code Standards

- All public functions and methods must have type annotations
- mypy strict mode must pass
- Ruff must pass with no warnings
- Maintain or improve test coverage (minimum 80%)

### Commit Messages

Use Conventional Commits for both commits and PR titles:

```
<type>(<optional-scope>): <short summary>
```

Examples:

- `feat: add JSON export support`
- `fix(api): handle empty input`
- `docs: update installation guide`

Recommended types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`,
`perf`, `build`.

### Changelog Policy

`CHANGELOG.md` (in [Keep a Changelog](https://keepachangelog.com/) format) is
the canonical, human-curated record of user-facing changes. Add an entry
under `[Unreleased]` for any user-facing change in the same PR that makes it.

GitHub's auto-generated release notes (via `.github/release.yml` categories)
are supplementary — useful for a quick PR-by-PR diff, but `CHANGELOG.md` is
what users should read to understand what changed in a release.

## Releasing

Releases are cut by pushing a `v*` tag. `.github/workflows/release.yml` then
runs ruff, mypy and pytest as a gate, checks the tag against
`project.version`, builds the sdist and wheel, smoke-tests the wheel, attests
its build provenance, publishes to PyPI and creates the GitHub Release. A
failing gate stops the run before anything is built or published. Nothing is uploaded by hand, and there is no PyPI
API token anywhere in this repository: the `publish` job authenticates to PyPI
with an OIDC identity through
[trusted publishing](https://docs.pypi.org/trusted-publishers/).

### One-time: register the trusted publisher on PyPI

**Do this before the first tag push, not after.** With no publisher registered
the workflow still runs and builds, then fails at `publish` when PyPI refuses
the OIDC token — leaving a tag behind with nothing published and no GitHub
Release.

Sign in to PyPI and add a GitHub publisher with exactly these values — they
must match the workflow, or PyPI rejects the token exchange:

| Field | Value |
| --- | --- |
| Owner | `your-username` |
| Repository name | `my-package` |
| Workflow name | `release.yml` |
| Environment name | `release` |

Where to enter them depends on whether the project exists on PyPI yet:

- **It exists**: *Manage project* → *Publishing* → *Add a new publisher*.
- **It does not exist** (the usual case for a first release): *Your account* →
  *Publishing* → add a
  [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/),
  which is what lets the very first upload create the project. A publisher
  cannot be attached to a project that is not there.

The `release` environment named above is the GitHub Actions environment the
`publish` job declares. Nothing has to be created on the GitHub side — a job
referencing an environment creates it — but PyPI compares the name against the
OIDC token's `environment` claim, so it has to be spelled the same in both
places. The environment is also where a required-reviewer rule would go if the
release ever needs a manual approval gate.

### Cutting a release

1. Land a release-prep pull request that sets `project.version` in
   `pyproject.toml` to the new version and turns the `[Unreleased]` section of
   `CHANGELOG.md` into a dated section for it, leaving an empty `[Unreleased]`
   behind. The tag and `project.version` are checked against each other by the
   workflow, so a mismatch stops the release before it builds anything.
2. Wait for CI to be green on `main`.
3. Tag the merge commit and push the tag:

   ```bash
   git checkout main && git pull
   git tag -a v0.1.0 -m "my-package 0.1.0"
   git push origin v0.1.0
   ```

4. Watch the run: `gh run list --workflow release.yml`, then
   `gh run watch <run-id>`.
5. Confirm the published artifact from outside this checkout, so nothing local
   can stand in for it:

   ```bash
   cd "$(mktemp -d)"
   uvx --with my-package python -c "import my_package; print(my_package.__version__)"
   ```

If the run fails, fix the problem and re-run the workflow against the same tag
(`gh workflow run release.yml --ref v0.1.0`) — that is what the
`workflow_dispatch` trigger is for. If the fix needs a code change, delete the
tag in both places (`git tag -d v0.1.0 && git push origin :refs/tags/v0.1.0`)
and tag again once it has landed.

**Once `publish` has succeeded the version is on PyPI for good** — PyPI does
not allow re-uploading a version, even a deleted one — so the fix for a bad
release is another release.

## Getting Help

If something is unclear, open an issue or start a discussion. We're happy to
help you get started.
