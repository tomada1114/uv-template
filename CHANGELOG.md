# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `.claude/settings.json` with a SessionStart hook that runs `just install`
  (falling back to `uvx --from rust-just just install` when `just` is
  missing) at the start or resume of a Claude Code cloud session, where
  `CLAUDE_CODE_REMOTE=true`; locally it exits at once
- An optional LLM layer. The core gains `LlmPort` (`complete(messages, *,
  model=None, max_tokens, timeout)` returning text, the answering model, the
  finish reason, and token usage) and the `LlmError` family; the adapters are
  `FakeLlm` for tests, `ClosedLlm`, and `OpenRouterLlm` over OpenRouter's chat
  completions endpoint, with 2 retries on 429, 502, 503, or a failed
  connection, `Retry-After` honored up to 8 seconds, and `timeout` as the
  call's budget, enforced between network phases rather than as a hard cutoff. `httpx` is added to a new optional extra, `ai`
  (`uv sync --extra ai`), and stays in the `dev` group; without
  `OPENROUTER_API_KEY` the layer stays closed and imports neither `httpx` nor
  the OpenRouter adapter, and `MY_APP_LLM_MODEL` picks the default model
  (`deepseek/deepseek-v4.1-flash`). The API answers an LLM error with 503
  (not configured), 429, 504, or 502. No route uses it yet; the new
  `integrating-llm` skill shows how to wire one, test it, or remove the layer
- `just check-harness`, part of `just verify` (CI's test shards run it too): a
  pytest suite in `tests/harness/` that fails on cross-file drift in the agent
  harness — a skill frontmatter with a key other than `name`/`description`, a
  `name` that is not its directory, a description that is not a `>` block, not
  ASCII, or over 600 characters, a body over 200 lines, or a nested `SKILL.md`;
  an `AGENTS.md` Skills table that disagrees with `.agents/skills/`; a
  `just <recipe>` that AGENTS.md, CLAUDE.md, a skill (its scripts included), or
  `.github/**` names but the justfile lacks; a required ruleset context that is
  not an unskippable every-PR job (moved from `tests/test_apply_ruleset.py`, its
  workflow scanner now shared in `tests/harness/_workflows.py`, and now also
  failing a `branches`, `branches-ignore`, or `types` filter that skips some pull
  requests to main); a label pr-label.yml, an issue form or Markdown template, or
  dependabot.yml applies that `.github/labels.yml` does not declare exactly once
  (moved from `tests/test_sync_labels.py`); and workflow hygiene — a `uses:` not
  pinned to a commit SHA with a `# v` comment, a job without `timeout-minutes`,
  top-level `permissions` wider than `contents: read`, a checkout that keeps its
  credentials, `pull_request_target`, `continue-on-error`, `|| true`, or a
  concurrency that can cancel a push run on main. The Product check stays
  `tests/test_product_section.py`, which the recipe also runs
- The harness's ruleset check now also fails a required job with `needs:` that
  has no step failing when a needed job's result is not `success` (as
  `Coverage`'s "Fail when a test shard did not succeed" step does), so such a
  job can no longer go green over a failed needed job. The step is read as
  text and counts only in the shapes `tests/harness/_needs.py` lists; a job no
  ruleset requires is not read
- The harness's workflow hygiene check now also reads composite actions under
  `.github/actions/` (`action.yml` or `action.yaml`): each step's `uses:` must be
  pinned to a commit SHA with a `# v` comment, a checkout must not keep its
  credentials, no step may set `continue-on-error`, and no line may end a
  command with `|| true`; an unreadable action is named by its path from the
  repository root
- The harness's recipe check now also reads every top-level Markdown file but
  CHANGELOG.md (README.md, CONTRIBUTING.md, TEMPLATE.md, ...), `docs/**` but the
  ADRs, the roadmap, and `docs/product/`, the agent definitions
  (`.claude/agents/`, `.codex/agents/`), `.pre-commit-config.yaml`, the
  `scripts/*.py` strings and comments, and composite actions' `run:` commands,
  so a renamed or removed `just` recipe they still name fails `just verify`. It
  now counts `just` only in a command's position, never in a comment, a quoted
  argument, or a `console`/`text`/`output` fence
- Seven process skills under `.agents/skills/` (mirrored to
  `.claude/skills/`): `writing-tests` and `placing-tests` (replacing
  `tests/AGENTS.md`), `tdd`, `managing-dependencies` (the `exclude-newer`
  window and the sign-off a new package needs), `changing-gates` (what
  weakening a gate means here, the pre-commit layer, required CI checks),
  `updating-docs`, and `writing-repo-scripts` (stdlib-only
  scripts, `ERR_*` reports on stderr, tests loaded through importlib)
- The `starting-an-app` skill: the order of work from "Use this template" to the
  first feature, which steps are a human's (ruleset, security settings, secrets),
  `just labels`, choosing the API, the CLI, or both, removing the sample to-do
  domain, and the first ADRs; `references/bootstrap.md` and
  `references/private-repository.md` hold the detail. `TEMPLATE.md` now points
  to it instead of listing the steps
- `AGENTS.md` gained a `## Product` section of four `TODO:` entries, now the one
  home of the app's non-goals (`steering-the-roadmap`, `triaging-issues`, and
  `roadmap.md` point at it instead of "Overview"), and
  `tests/test_product_section.py` fails while one is left once `.template-origin`
  exists (in the template it requires them)
- CI's `Template Bootstrap Smoke` job: bootstraps a scratch clone with sample
  values, fails on any surviving placeholder, fills the Product section, and runs
  `just verify` there. It is not a required check
- Six code-writing skills for the application layers, under `.agents/skills/`
  and mirrored to `.claude/skills/`: `writing-python` (module and function
  style, condensing AGENTS.md's `src/**` conventions), `designing-errors` (the
  `AppError` hierarchy, its HTTP status and CLI exit-code mappings),
  `designing-core-logic` (core, ports, adapters, settings, composition root),
  `building-api-routes` and `designing-clis` (each deleted along with its entry
  point), and `running-the-app` (a server of the agent's own on a free port,
  curl evidence, stopped before the turn ends, never the developer's)
- An application skeleton in `src/my_app/` (distribution and console script
  `my-app`): a framework-free `core` (frozen-dataclass domain model,
  `typing.Protocol` ports, services, an `AppError` base with
  `TodoNotFoundError`/`InvalidTodoError`), in-memory and stdlib-`sqlite3`
  `adapters` sharing one contract suite, a FastAPI `api` (`create_app`,
  `GET /healthz`, to-do routes), a Typer `cli` (`my-app todo
  add|list|complete|delete`, `my-app serve`), `MY_APP_*` settings via
  pydantic-settings, and one composition root for both entry points. Ruff's
  `TID251` banned-api rule and a test keep fastapi, typer, uvicorn, sqlite3,
  and httpx out of the core. The API answers domain errors with an
  `ErrorResponse` body (404 / 422, 400 for any other `AppError`); the CLI
  exits 1 for a domain error, 2 for a usage error, and 3 for an invalid
  `MY_APP_*` setting, with one line on stderr. `my-app todo` never imports
  FastAPI or uvicorn. Runtime dependencies: fastapi, uvicorn, typer,
  pydantic-settings; dev: httpx
- `just dev` (human-run API server with auto-reload) and `just run *ARGS`
  (the CLI through `uv run --locked my-app`)
- The main branch ruleset as code (`.github/rulesets/main.json`) and
  `just ruleset` (`scripts/apply_ruleset.py`), an admin-run upsert that never
  deletes
- `scripts/check_staged.py`, a pre-commit hook (`check-staged`) that refuses
  a commit staging a secret-shaped path (`.env*` and `.envrc*` except
  `.example`, `.sample`, and `.template` copies, `secrets/**`, `*.pem`,
  `*.key`, `id_rsa*`, personal agent settings) or credential-shaped content,
  read from the index; it also runs on merge commits (`pre-merge-commit`).
  `just install` now fails when the git hooks are missing (opt-out:
  `ALLOW_MISSING_GIT_HOOKS=1`; `CI=true` only warns). **Existing checkouts:
  re-run `just install`** to add the new `pre-merge-commit` hook
- `.check-staged-allow`, a committed allowlist for the `check-staged` secret
  gate, read from the index: `path <file>` exempts one exact file from the
  path rules and `content <file> <blob id>` exempts one exact staged content
  from the credential patterns, each below a `#` reason comment. Globs,
  directories, and `.` are refused (`ERR_STAGED_ALLOWLIST_TOO_BROAD`), and an
  entry the index no longer matches — a deleted or renamed file, edited
  content, a path no rule refuses — fails the commit
  (`ERR_STAGED_ALLOWLIST_STALE`) until it is removed; any allowlist error
  exits 3
- Security scanning workflows: CodeQL (`python`, `actions`), OSV-Scanner
  on `uv.lock`, Dependency Review with a license allow-list, and a weekly
  full-history gitleaks audit with a checksum-verified binary
- A safer bootstrap flow with validated package/repository names, collision
  checks, syntax-safe metadata quoting, and protection against rewriting
  untracked, symlinked, or secret files after a Git failure
- Initial project structure
- `scripts/bootstrap.py` deterministic template initializer: renames the
  package and replaces every placeholder (`my-package`, `my_package`,
  `uv-template`, `your-username`, `Your Name`, `you@example.com`, and the
  description) across tracked files, then finishes the new project off —
  current year in `LICENSE`,
  `CHANGELOG.md` reset to an empty skeleton, `uv lock` run (warn-only), and
  its own scaffolding deleted unless `--keep-bootstrap` is passed.
  `--github-user` is now required, since omitting it shipped a dead
  security-report URL in `.github/ISSUE_TEMPLATE/config.yml`
- `just verify` — a non-mutating `lock-check -> agents-check -> lint -> test-skills -> test` gate
  for PRs and completion claims, distinct from `just check` (which mutates
  the tree via `fmt` first and never proves the committed tree is green)
- `just test-durations` and `just worktree-clean`
  recipes (the last removes `.claude/worktrees/*` whose branch already has
  a merged PR)
- A sharded CI test job (`pytest-split` + `pytest-xdist`, 4 shards) with a
  `coverage` job that downloads and combines the shards' data and enforces
  `--cov-fail-under=80` once, replacing the single-process test run
- `zizmor` security lint for GitHub Actions workflows, wired into both CI
  and pre-commit
- PR auto-labeling by Conventional Commit type
- `TEMPLATE.md`, holding the template's own Design Philosophy and setup
  checklist so `README.md` ships as a plain application README
- `.devcontainer/devcontainer.json` for a ready-to-use dev environment
- `.github/ISSUE_TEMPLATE/config.yml` disabling blank issues and linking
  security reports to GitHub Security Advisories
- Dependabot cooldown and the `tool.uv.exclude-newer` supply-chain cutoff,
  documented in the `pyproject.toml` convention in `AGENTS.md`
- `AGENTS.md` as the canonical, tool-agnostic agent guide (previously a
  symlink to `CLAUDE.md`, which breaks on Windows checkouts)
- `.agents/hooks/guard.py` PreToolUse guard blocking writes to
  `uv.lock`/`.env*`/`secrets/**` (via Edit/Write or shell commands),
  `git commit --no-verify`, and plain force-pushes
- `.agents/hooks/stop_check.py` Stop-hook gate running ruff (lint + format
  check) and mypy before an agent turn ends when Python files changed
- Committed Claude Code permission allowlist for local development
  commands — commit/push/PR creation stay behind approval

### Changed

- Python dependencies arrive by Dependabot: `.github/dependabot.yml` gains a
  monthly `uv` entry with `cooldown.default-days: 14`, one group for minor and
  patch updates (each major its own PR), `labels: ["dependencies"]` (the
  `github-actions` entry pins the same label), and an open-PR limit of 3.
  `[tool.uv] exclude-newer` is now the relative `"14 days"`, equal to that
  cooldown, instead of a fixed date moved by hand each month, and the expired
  `virtualenv`/`python-discovery` `exclude-newer-package` entry is gone.
  `managing-dependencies` replaces its monthly procedure with "Dependabot
  proposes, a human merges via `merging-dependency-prs`", which now surveys
  and reviews `uv` PRs (`survey_prs.py` classifies `dependabot/uv/...`
  branches as `uv`); `scripts/bootstrap.py` no longer rewrites
  `exclude-newer`. `[tool.uv] required-version = ">=0.11.8"` now refuses an
  older uv, which cannot read the relative window's lockfile form
- CI, CodeQL, and OSV-Scanner key their concurrency group on the commit SHA
  outside a pull request, and CI cancels only superseded pull-request runs, so
  no push to main is cancelled or replaced while pending; `check-pr-title.yml`
  and `pr-label.yml` move their `pull-requests` scope from the top level onto
  the job, leaving `permissions: {}` at the top
- `authoring-skills` names the harness wherever it said no check enforced a rule
- `AGENTS.md` keeps only what every task needs — Overview, Product, Quick
  Reference, Validating a change, Architecture, Skills, Sub-agents, Security
  and human approval, Enforcement layers — and its conventions and
  procedures moved into skills; the GitHub settings a new repository enables
  moved to `starting-an-app`'s `references/github-settings.md`.
  `tests/AGENTS.md` is gone. `create-pr` and `smart-commit` are refreshed
  from the sibling templates: frontmatter is `name` and `description` only,
  and smart-commit carries a recovery table for each pre-commit hook
- **Breaking:** `scripts/bootstrap.py` is rebuilt for the application template.
  It replaces `my-app`, `my_app`, `My App` (the new display-name placeholder),
  `MY_APP_`, `your-username/uv-template`, and `Your Name`; validates every value
  and computes every edit in memory before the first write; refuses a dirty work
  tree, a run from outside its own checkout, a reserved name (the layers' names,
  the placeholders, the packages the app imports, the `scripts/` stems, Python
  keywords, stdlib modules), and a second run; removes `<!-- template-only -->`
  blocks and the template-only files, deleting itself last; writes
  `.template-origin`; and runs `uv lock` and the formatter. A write that fails
  part-way names what was done and the `git restore`/`git clean` recovery. `--email` is gone and no email address is written: the new optional
  `--contact-url` fills the contact sentences in `SECURITY.md` and
  `CODE_OF_CONDUCT.md`, which otherwise point at the repository's private
  vulnerability reporting and issue tracker. `--author` and `--description` are
  now required; `--github-repository` also takes `OWNER/NAME`
- **Breaking:** the package placeholder is now `my-app`/`my_app`, and
  `scripts/bootstrap.py` renames those instead of `my-package`/`my_package`
- `scripts/bootstrap.py` accepts a GitHub repository name independent of the
  distribution name and replaces placeholders without cascading into new
  values
- Coverage now names the measured code once, in `[tool.coverage.run]
  source`, so the justfile / CI / CONTRIBUTING command is just `pytest
  --cov ...` and survives the bootstrap rename untouched
- `pytest` no longer runs with `-v` by default; the unused `slow` marker
  is gone
- The committed permission allowlist covers the remaining `just` recipes,
  `uv add`, and read-only `git`/`gh` inspection commands, and every entry
  is normalized to the `:*` form. Commit, push, and PR creation still
  require approval
- The Python convention in `AGENTS.md` keeps the Performance section to a
  two-line "profile first" rule; the previous micro-optimization list drove
  over-engineering in libraries far too small to need it. The base-exception
  rule is conditional on the package raising more than one domain error
- `tests/AGENTS.md` is reduced to a short essentials block, in
  place of a 6-category mandatory edge-case matrix that no small library
  can satisfy honestly
- `SECURITY.md` states best-effort response instead of a 48-hour /
  7-day SLA that a volunteer maintainer cannot keep across many repos
- `CODE_OF_CONDUCT.md` points reports at GitHub Security Advisories and the
  maintainer email instead of "the issue tracker or email"
- The PR template checklist is three items (`just check`, docs, breaking
  changes) instead of seven, and the bug report form requires only
  Description, Reproduction, and Version
- Dependabot drops the `pip` ecosystem and groups GitHub Actions into a
  single monthly PR. The `pip` ecosystem cannot manage PEP 735
  `[dependency-groups]` plus `uv.lock`, and `exclude-newer` blocked the
  bumps it proposed; Python dependencies now arrive through the `uv`
  ecosystem (the entry above)
- zizmor findings are now exempted with inline `# zizmor: ignore[...]`
  comments instead of line numbers in `.github/zizmor.yml` (removed), which
  stopped matching whenever a workflow shifted by a line
- Moved coverage enforcement (`--cov-fail-under=80`) out of pytest
  `addopts` and into `just test` / CI, so a single test can be run in
  isolation without failing the coverage gate
- Scoped all workflow permissions to job level, added `timeout-minutes`
  to every job, added `--locked` to every `uv sync` in CI, and disabled
  checkout credential persistence
- Simplified `src/my_package/__init__.py`'s version resolution to the
  standard `importlib.metadata.version()` pattern, dropping the ~50-line
  local-pyproject-walking fallback chain
- Replaced the bespoke `no-commit-to-main` pre-commit hook with the
  pre-commit-hooks builtin `no-commit-to-branch`
- Unified mypy targets (`src scripts tests`) across justfile, CI,
  and pre-commit
- Expanded ruff rule set (`D`, `PT`, `N`, `TRY`, `EM`, `DTZ`, `RSE`,
  `PGH`) to match the Python convention in `AGENTS.md`; renamed `TCH` -> `TC`
- The post-edit format hook now formats only the edited Python file and
  surfaces failures to the agent, replacing the repo-wide ruff run that
  suppressed all errors
- `CLAUDE.md` is now a thin `@AGENTS.md` import plus Claude Code
  specifics; the Python convention in `AGENTS.md` no longer restates rules
  ruff already enforces mechanically
- `just fmt` now runs `ruff check --fix` before `ruff format` (ruff's
  recommended order, matching the post-edit hook), so lint autofixes can
  no longer leave formatting drift behind
- Python baseline moved to 3.14 across the whole toolchain
  (`requires-python`, ruff `target-version`, mypy `python_version`,
  `.python-version`, the devcontainer image, and every CI workflow),
  replacing the previous 3.12 floor and the 3.12/3.13/3.14 CI test matrix
- `AGENTS.md` gained a `## Git Workflow` section (every change goes through
  a branch and a PR, matching the `no-commit-to-branch` hook) and a short
  `## Sources of Truth` table; the mocking guidance now allows asserting a
  call count when the call itself is the contract (retry/rate-limit
  behavior, a skipped step, proving no network call happened); the
  300-line/40-line design rule is now a review trigger, not an absolute limit
- The PR template's first checklist item is now `just verify` instead of
  `just check`, matching the non-mutating gate; `create-pr` was
  updated to match

### Removed

- The library placeholder `src/my_package` (`add()`) and its tests, replaced
  by the application skeleton
- The agent hooks under `.agents/hooks/` (`guard.py`, `format.py`,
  `stop_check.py`, `hook_payload.py`) and their wiring in
  `.claude/settings.json` and `.codex/hooks.json`; the guard rails now run as
  git hooks for every author, and `AGENTS.md` maps each former behavior to its
  replacement
- **Breaking:** library publishing — the template now targets applications.
  The PyPI release workflow, the distribution smoke test (`just build`,
  `just smoke`), the mkdocs site (`just docs`, `just docs-check`, the `docs`
  dependency group), `py.typed`, and the `release-workflow` skill are gone
- The empty `tests/conftest.py` — nothing needed it
- The Scorecard, `pip-audit`, and dependency-review workflows. With zero
  runtime dependencies they audit only this repo's dev tooling, and both
  Scorecard and dependency review need a public repo or GHAS, which a
  freshly spawned private repo does not have
- The Codecov upload step and README badge — coverage is already gated in
  CI by `--cov-fail-under=80`, and the upload needs a per-repo
  `CODECOV_TOKEN` that every spawned repo would have to provision

### Fixed

- Security Audit no longer lets a dispatched scan replace a pending scheduled
  one (or the reverse): outside pull requests its concurrency group is keyed
  per run. Dependency Review's concurrency comment now describes what it does
  (cancelling superseded PR runs) instead of a copied ci.yml comment.
- Switched to PEP 639 license metadata (`license-files`, dropped the
  redundant OSI trove classifier)
- `CONTRIBUTING.md`'s manual mypy command now includes `tests`, matching
  justfile/CI/pre-commit
- The `create-pr` skill re-checks the working tree after `just check` so
  formatting changes cannot be left uncommitted behind a green checklist
- `.agents/hooks/stop_check.py` now filters its mypy paths by existence, so
  a spawned repo without `scripts/` is no longer blocked from ever ending a
  turn by mypy's "Cannot read file" error
- `.agents/hooks/format.py` resolves the project root from the hook script
  location instead of the payload `cwd`, which silently skipped formatting
  when the session ran in a subdirectory
- `.agents/hooks/guard.py` now blocks `gh pr merge --admin`, previously
  forbidden only in prose
- The `create-pr` and `smart-commit` skills use the backtick form
  (`` !`cmd` ``) for dynamic context; the previous bare `!cmd` lines were
  literal text, so both skills ran with no injected context at all
- `.claude/settings.json` now resolves its hook scripts via
  `${CLAUDE_PROJECT_DIR}` instead of `$(git rev-parse --show-toplevel)`,
  which broke every Bash/Write call once a session's shell `cd`'d into a
  second working-directory repository lacking `.agents/hooks/`

[Unreleased]: https://github.com/your-username/uv-template/commits/main
