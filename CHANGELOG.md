# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial project structure
- `scripts/bootstrap.py` deterministic template initializer: renames the
  package and replaces every placeholder (`my-package`, `my_package`,
  `uv-template`, `your-username`, `Your Name`, `you@example.com`, and the
  description) across tracked files, then finishes the new project off —
  current year in `LICENSE`, `exclude-newer` moved to today-14d,
  `CHANGELOG.md` reset to an empty skeleton, `uv lock` run (warn-only), and
  its own scaffolding deleted unless `--keep-bootstrap` is passed.
  `--github-user` is now required, since omitting it shipped a dead
  security-report URL in `.github/ISSUE_TEMPLATE/config.yml`
- Python 3.14 support in the CI test matrix and trove classifiers
- `zizmor` security lint for GitHub Actions workflows, wired into both CI
  and pre-commit
- PR auto-labeling by Conventional Commit type, so the release changelog
  categories actually populate
- `TEMPLATE.md`, holding the template's own Design Philosophy and setup
  checklist so `README.md` ships as a plain library README. The checklist
  gained two previously missing but required steps: registering PyPI
  Trusted Publishing (environment `release`) and enabling GitHub Pages
  from the `gh-pages` branch
- A PR-time `mkdocs build --strict` job in CI, so documentation breakage
  surfaces on the pull request instead of after the merge
- `workflow_dispatch` on the release workflow, so a failed publish can be
  retried without deleting and re-pushing the tag
- `.devcontainer/devcontainer.json` for a ready-to-use dev environment
- `.github/ISSUE_TEMPLATE/config.yml` disabling blank issues and linking
  security reports to GitHub Security Advisories
- Dependabot cooldown and the `tool.uv.exclude-newer` supply-chain cutoff,
  documented in `.claude/rules/pyproject.md` together with the manual
  Python dependency update procedure
- `AGENTS.md` as the canonical, tool-agnostic agent guide (previously a
  symlink to `CLAUDE.md`, which breaks on Windows checkouts)
- `.claude/hooks/guard.py` PreToolUse guard blocking writes to
  `uv.lock`/`.env*`/`secrets/**` (via Edit/Write or shell commands),
  `git commit --no-verify`, and plain force-pushes
- `.claude/hooks/stop_check.py` Stop-hook gate running ruff (lint + format
  check) and mypy before an agent turn ends when Python files changed
- Committed Claude Code permission allowlist for local development
  commands — commit/push/PR creation stay behind approval
- `.claude/skills/release-workflow/SKILL.md` covering the full release
  path: preflight, version pick, release PR, tag, and pipeline watch

### Removed

- The empty `tests/conftest.py` — nothing needed it
- `docs/getting-started.md`, and the hand-maintained copy of the README in
  `docs/index.md`. The docs home page now includes `README.md` via
  `--8<--`, the same way `docs/contributing.md` includes `CONTRIBUTING.md`,
  so a public API change no longer has to be mirrored into four files
- The Scorecard, `pip-audit`, and dependency-review workflows. With zero
  runtime dependencies they audit only this repo's dev tooling, and both
  Scorecard and dependency review need a public repo or GHAS, which a
  freshly spawned private repo does not have
- The Codecov upload step and README badge — coverage is already gated in
  CI by `--cov-fail-under=80`, and the upload needs a per-repo
  `CODECOV_TOKEN` that every spawned repo would have to provision
- The redundant `test` job in the release workflow; the same commit
  already passed CI on `main` before it was tagged

### Changed

- Coverage now names the measured code once, in `[tool.coverage.run]
  source`, so the justfile / CI / CONTRIBUTING command is just `pytest
  --cov ...` and survives the bootstrap rename untouched
- `pytest` no longer runs with `-v` by default; the unused `slow` marker
  is gone
- The committed permission allowlist covers the remaining `just` recipes,
  `uv add`, and read-only `git`/`gh` inspection commands, and every entry
  is normalized to the `:*` form. Commit, push, and PR creation still
  require approval
- `.claude/rules/python.md`'s Performance section is now a two-line
  "profile first" rule; the previous micro-optimization list drove
  over-engineering in libraries far too small to need it. The base-exception
  rule is conditional on the package raising more than one domain error
- `.claude/rules/testing.md` is reduced to a short essentials block, in
  place of a 6-category mandatory edge-case matrix that no small library
  can satisfy honestly
- `SECURITY.md` states best-effort response instead of a 48-hour /
  7-day SLA that a volunteer maintainer cannot keep across many repos
- `CODE_OF_CONDUCT.md` points reports at GitHub Security Advisories and the
  maintainer email instead of "the issue tracker or email"
- The PR template checklist is three items (`just check`, docs, breaking
  changes) instead of seven, and the bug report form requires only
  Description, Reproduction, and Version
- Dependabot now covers GitHub Actions only, monthly and grouped into a
  single PR. The `pip` ecosystem cannot manage PEP 735
  `[dependency-groups]` plus `uv.lock`, and `exclude-newer` blocked the
  bumps it proposed; Python dependencies are updated manually instead
- zizmor findings are now exempted with inline `# zizmor: ignore[...]`
  comments instead of line numbers in `.github/zizmor.yml` (removed), which
  stopped matching whenever a workflow shifted by a line
- The docs deploy no longer triggers on `pyproject.toml` / `uv.lock`, so a
  dependency bump no longer redeploys the documentation
- The PR title check no longer runs on `synchronize` — the title cannot
  change on push
- Moved coverage enforcement (`--cov-fail-under=80`) out of pytest
  `addopts` and into `just test` / CI, so a single test can be run in
  isolation without failing the coverage gate
- Restructured the release pipeline: a dedicated `build` job now builds
  and attests provenance once; `publish` and the GitHub Release both
  consume that artifact instead of rebuilding
- Scoped all workflow permissions to job level, added `timeout-minutes`
  to every job, added `--locked` to every `uv sync` in CI, and disabled
  checkout credential persistence outside the docs deploy job
- Simplified `src/my_package/__init__.py`'s version resolution to the
  standard `importlib.metadata.version()` pattern, dropping the ~50-line
  local-pyproject-walking fallback chain
- Replaced the bespoke `no-commit-to-main` pre-commit hook with the
  pre-commit-hooks builtin `no-commit-to-branch`
- Unified mypy targets (`src scripts tests`) across justfile, CI,
  release, and pre-commit
- Expanded ruff rule set (`D`, `PT`, `N`, `TRY`, `EM`, `DTZ`, `RSE`,
  `PGH`) to match `.claude/rules/python.md`; renamed `TCH` -> `TC`
- The post-edit format hook now formats only the edited Python file and
  surfaces failures to the agent, replacing the repo-wide ruff run that
  suppressed all errors
- `CLAUDE.md` is now a thin `@AGENTS.md` import plus Claude Code
  specifics; `.claude/rules/python.md` no longer restates rules ruff
  already enforces mechanically
- `just fmt` now runs `ruff check --fix` before `ruff format` (ruff's
  recommended order, matching the post-edit hook), so lint autofixes can
  no longer leave formatting drift behind

### Fixed

- Switched to PEP 639 license metadata (`license-files`, dropped the
  redundant OSI trove classifier)
- `CONTRIBUTING.md`'s manual mypy command now includes `tests`, matching
  justfile/CI/pre-commit
- The `create-pr` skill re-checks the working tree after `just check` so
  formatting changes cannot be left uncommitted behind a green checklist
- `.claude/hooks/stop_check.py` now filters its mypy paths by existence, so
  a spawned repo without `scripts/` is no longer blocked from ever ending a
  turn by mypy's "Cannot read file" error
- `.claude/hooks/format.py` resolves the project root from
  `CLAUDE_PROJECT_DIR` instead of the payload `cwd`, which silently skipped
  formatting when the session ran in a subdirectory
- `.claude/hooks/guard.py` now blocks `gh pr merge --admin`, previously
  forbidden only in prose
- The `create-pr` and `smart-commit` skills use the backtick form
  (`` !`cmd` ``) for dynamic context; the previous bare `!cmd` lines were
  literal text, so both skills ran with no injected context at all

[Unreleased]: https://github.com/your-username/my-package/commits/main
