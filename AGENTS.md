# Project Guide

## Overview

This is a Python application built with [uv](https://docs.astral.sh/uv/) and
[hatchling](https://hatch.pypa.io/). It uses a strict `src/` layout with
comprehensive type checking and linting.

It ships a framework-free core with two entry points over it: a FastAPI HTTP
API and a Typer CLI (`my-app`). The sample domain is a to-do list — replace it
with your own, and delete whichever entry point you do not need.

## Quick Reference

The recipes are grouped by who runs them: finite checks an agent runs to
verify its own work, a server that never ends on its own, and the recipes that
write to GitHub.

### Checks and tasks an agent runs

```bash
just install         # Install dependencies and git hooks when .git/ is present
just setup           # Alias for just install (first-time setup)
just fmt             # Format code (ruff check --fix + ruff format)
just lint            # Lint (ruff check) + type check (mypy)
just test            # Run tests in parallel with coverage
just test-durations  # Regenerate the pytest-split duration file used by CI shards
just check           # Mutating dev check: fmt → lint → test
just lock            # Update uv.lock after dependency changes
just verify          # Non-mutating gate: lock-check → agents-check → lint → test-skills → test
just test-skills     # Run the unittest suites bundled under .agents/skills/*/scripts/tests
just run *ARGS       # Run the CLI, e.g. `just run todo list` (uv run --locked my-app ...)
just worktree-clean  # Remove agent worktrees under .claude/worktrees with a merged PR
just agents-sync     # Regenerate the .claude/skills mirror from .agents/skills
just agents-check    # Fail when the skills mirror has drifted
just clean           # Remove build artifacts and caches
```

### Long-running — human-run

```bash
just dev             # Serve the API on http://127.0.0.1:8000 with auto-reload; runs until stopped
```

`just dev` is the developer's server: never start, stop, or restart it, and
never bind its port. To see something only a running server shows, prefer a
`TestClient` test; failing that, start `uv run --locked my-app serve --port
<free port>`, verify against it, and stop it before your turn ends. Never
leave a server you started running.

### Writes to GitHub

```bash
just labels          # Create/update GitHub labels from .github/labels.yml (ask first)
just ruleset         # Apply .github/rulesets/main.json to GitHub (admin-only human step; never an agent)
```

Without Just: replace `just <cmd>` with the corresponding `uv run` commands
in the `justfile`. Run a single test with
`uv run --locked pytest tests/test_<module>.py::test_<name>`.

`just check` mutates the tree (it runs `fmt` first), so it never proves the
*committed* tree is green. `just verify` does not mutate anything — it is the
gate for a PR or a completion claim.

## Validating a change

Run the narrowest check that can fail while iterating, then `just verify` before
a completion claim. `just verify` on every edit is slow enough that it stops
being run at all.

| What you changed | The narrowest check that can fail |
|---|---|
| A module under `src/my_app/<layer>/` | `uv run --locked pytest tests/<layer>/` |
| `settings.py` or `composition.py` | `uv run --locked pytest tests/test_settings.py tests/test_composition.py` |
| A repository adapter | `uv run --locked pytest tests/adapters/test_repository_contract.py` |
| One test | `uv run --locked pytest tests/test_<module>.py::test_<name>` |
| Any Python file's lint or types | `uv run --locked ruff check <file>`, then `uv run --locked mypy src scripts tests` |
| A script under `scripts/` | `uv run --locked pytest tests/test_<script>.py` |
| A skill under `.agents/skills/` | `just agents-sync && just agents-check && just test-skills` |
| Dependencies in `pyproject.toml` | `uv lock`, `uv sync --all-groups --locked`, then `just verify` |
| A workflow under `.github/workflows/` | `uv run --locked pre-commit run zizmor --all-files` |
| Markdown or other prose | `uv run --locked pre-commit run typos --files <file>` |

## Architecture

```
src/my_app/
├── core/            # Framework-free: domain model, ports (Protocols), services, errors
├── adapters/        # Port implementations: in-memory and SQLite (stdlib sqlite3) repositories
├── api/             # FastAPI: create_app(settings) factory, routers, Pydantic schemas
├── cli/             # Typer: `my-app todo add|list|complete|delete`; serve.py holds `my-app serve`
├── settings.py      # pydantic-settings, read from MY_APP_* environment variables
└── composition.py   # Composition root: wires adapters into services for both entry points
```

- Dependencies point inward: `api/` and `cli/` call `core/` services and get
  them only from `composition.build_container`; `adapters/` implement
  `core/ports.py`; `core/` imports nothing outside the stdlib and itself.
  Ruff's `TID251` (banned-api in `pyproject.toml`) and
  `tests/core/test_imports.py` fail the build when `core/` imports fastapi,
  typer, uvicorn, sqlite3, or httpx.
- Domain errors derive from `core.errors.AppError`; each entry point maps
  them in one place. The API's one `AppError` handler in `api/app.py` answers
  404 (not found), 422 (invalid input), or 400 (any other `AppError`) with an
  `ErrorResponse` body. The CLI's `cli/errors.py` owns every exit code:
  0 success, 1 domain error, 2 usage error (Typer's own), 3 invalid
  `MY_APP_*` setting — each failure is one line on stderr, no traceback.
- The CLI never imports the API at import time: `cli/serve.py` is the only
  bridge, and it imports FastAPI and uvicorn inside the command.
- Removing an entry point is a deletion, never a core change:
  - Without the API: delete `src/my_app/api/`, `src/my_app/cli/serve.py` and
    its `app.command()(serve)` line in `cli/main.py`, `tests/api/`,
    `tests/cli/test_serve.py`, the `fastapi` and `uvicorn` runtime
    dependencies and the `httpx` dev dependency (then `uv lock`), the
    `just dev` recipe, and the `fastapi.*` entries and the `api/**`
    per-file-ignore in `pyproject.toml`'s ruff config.
  - Without the CLI: delete `src/my_app/cli/`, `tests/cli/`,
    `[project.scripts]`, the `typer` runtime dependency (then `uv lock`), the
    `just run` recipe, and the `typer.*` entries and the `cli/**`
    per-file-ignore in the ruff config. Keep `uvicorn`: `just dev` serves the
    API with it.
- A new repository implements `core.ports.TodoRepository` and joins the one
  contract suite in `tests/adapters/test_repository_contract.py`.
- Pydantic stays at the boundaries (`api/schemas.py`, `settings.py`); the core
  uses frozen dataclasses.
- Tests mirror the layers: `tests/core/`, `tests/adapters/`, `tests/api/`,
  `tests/cli/`, plus `tests/test_settings.py` and `tests/test_composition.py`.
- Internal modules can use a leading underscore (`_internal.py`)
- Separate concerns: one module per logical unit
- Update README.md when a command, setting, or behavior it documents changes

## Sources of Truth

| Concern | Canonical source |
|---|---|
| Tooling and quality commands | `justfile`, `pyproject.toml`, CI workflows |
| Layer boundaries | `[tool.ruff.lint.flake8-tidy-imports.banned-api]` and its per-file-ignores in `pyproject.toml` |
| HTTP routes and CLI commands | `src/my_app/api/routers/`, `src/my_app/cli/` |
| Configuration keys | `src/my_app/settings.py` (`Settings`, prefix `MY_APP_`) |
| Current execution status | Git, fresh test output, and CI — never prose or test counts in a prompt |

## Skills

Skills are authored under `.agents/skills/` — the path Codex CLI reads — and
mirrored byte for byte into `.claude/skills/`, the only path Claude Code reads.
Edit `.agents/skills/` only, then run `just agents-sync` and commit both trees;
drift fails `just agents-check`, `tests/test_sync_agents.py`, the pre-commit
hook, and CI. Both copies are real files, never symlinks: a symlink breaks on
some clones and makes Codex register a nested `references/SKILL.md` as a skill.

| Skill | Load it when |
|---|---|
| `authoring-skills` | adding, editing, or reviewing a skill under `.agents/skills/`, or a skill never fires |
| `building-api-routes` | adding or changing an HTTP route, request or response model, or API dependency, and the TestClient tests for it |
| `create-pr` | opening or updating a pull request |
| `designing-clis` | adding or changing a `my-app` command, its arguments, or its output, and the CliRunner tests for it |
| `designing-core-logic` | adding a use case, domain rule, port, adapter, or `MY_APP_*` setting, or wiring the composition root |
| `designing-errors` | adding a failure mode, or choosing the HTTP status or exit code a domain error becomes |
| `merging-dependency-prs` | landing open Dependabot pull requests (GitHub Actions bumps) |
| `recording-architecture-decisions` | a change owes an ADR, or an ADR under `docs/architecture/` is proposed, accepted, or superseded |
| `running-the-app` | running the CLI or a server of your own to observe a change, and stopping that server afterwards |
| `shipping-issues` | shipping the next issue or the whole backlog: rank, implement, review, PR, CI, merge |
| `smart-commit` | grouping working-tree changes into commits |
| `steering-the-roadmap` | asked what to work on next, or the Now / Next / Later roadmap moves |
| `triaging-issues` | filing, labelling, or prioritizing an issue, or recording a problem found outside the task |
| `writing-python` | writing or reviewing any Python module, class, or function: typing, imports, docstrings, idioms |

## Sub-agents

A skill runs every step inline by default. On a host that can hand a step to a
named sub-agent, a step marked for a tier may go to one of three:

| Tier | Effort | Takes |
|---|---|---|
| `executor` | low | a settled spec with a clear pass/fail: implementing it, adding tests, getting a check green, bulk edits, research that only collects |
| `architect` | high | design judgment, review and bug finding, multi-file work, synthesis, a spec that still has holes |
| `worker` | medium | single-shot, tool-free writing or checking from a complete brief |

Each tier is defined once per host, and both hosts describe the same three:
`.claude/agents/<tier>.md` for Claude Code pins a model alias (`opus` for
`executor` and `architect`, `sonnet` for `worker` — never a dated model ID) and
an `effort`; `.codex/agents/<tier>.toml` for Codex CLI sets only
`model_reasoning_effort` and omits `model`, so the session's model is
inherited. The instructions are the same text in both files, and
`tests/test_agent_tiers.py` holds the two directories to that.

- Neither file declares a permission — no `sandbox_mode`, no tool list.
- Codex CLI loads `.codex/` only for a trusted project; in an untrusted
  checkout a step marked for a tier runs inline.
- Codex CLI ships a built-in `worker`; `.codex/agents/worker.toml` replaces it
  inside this repository on purpose.

## Personal settings

No permission rule, model choice, or plugin marketplace is committed. Keep them
in your own `~/.claude/settings.json` / `~/.codex/config.toml`, or in the
gitignored `.claude/settings.local.json` and `.codex/rules/local.rules`. A
committed allowlist would force one person's trust decisions on every
repository created from this template.

## Review Checklist

Before submitting a PR:

1. `just verify` passes (lock check, skills mirror, lint, skill tests, tests)
2. New public functions have type annotations and docstrings
3. Tests cover the new functionality
4. No unnecessary dependencies added

## Git Workflow

- Every change goes through a branch and a pull request; the
  `no-commit-to-branch --branch main` pre-commit hook enforces this.
- Keep the implementation, its regression test, and any required doc update in
  the same logical commit.
- Run `just verify` before a completion claim, on any code change.

## Security and human approval

- **Commit, push, and pull request need a human's sign-off** — given per
  request, or by one of the [standing exceptions](#standing-exceptions) below.
  Nothing in the repository blocks a force-push or `gh pr merge --admin`; this
  instruction is the rule itself.
- Never bypass a git hook — no `--no-verify`, no `SKIP=<hook id>`, no edit to
  `.git/hooks/`. `--no-verify` switches off the secret gate of the
  [pre-commit layer](#pre-commit-layer) along with everything else.
- Never weaken a gate to make a run pass: no lowered coverage threshold, no
  removed ruff rule, no `noqa`, `type: ignore`, or per-file ignore without a
  written reason, no skipped or deleted test, no removed `--locked`. If a gate
  is wrong, say so and let a human decide.
- When a command is denied — by a permission setting, a hook, or a human —
  re-spelling it (`bash -c '…'`, an alias, a wrapper script) is forbidden. Stop
  and ask.

### Standing exceptions

Invoking a skill that lists the commits or remote writes it makes is the
sign-off for exactly those, for that invocation only:

- `shipping-issues`: the writes its `SKILL.md` lists — priority and status
  labels, syncing label definitions from `.github/labels.yml` with
  `just labels`, pushing its own branches, creating the pull request, merging
  it once CI passes, filing and labelling follow-up issues and the comments it
  posts, and deleting the branches it created.
- `create-pr`: pushing the current branch, `gh pr create` for it, and
  `gh pr edit` on its own open pull request — never a force-push and never a
  merge.
- `smart-commit`: the commits it makes on the current branch, and pushing that
  branch only when the request asked for a push — never a force-push and never
  `main`.

One request is a standing exception too: the owner explicitly asking for an
issue ("file an issue for this") is the sign-off for the `gh issue create` of
each issue that request asks for, with the labels `triaging-issues` gives it.
An issue the agent would file from a friction it noticed on its own is drafted
in the reply and waits for a yes.

None of them covers a force-push or other history rewrite, `--no-verify` or
any other hook bypass, weakening a gate, or adding a dependency — a new
dependency is proposed and the agent stops for sign-off.

## GitHub settings a new repository must enable

### Main branch ruleset

`.github/rulesets/main.json` protects the default branch: no deletion, no
force-push, a pull request for every change (0 approvals), and the required
status checks. `just ruleset` creates it, or updates it by name, through
`gh api`; it never deletes a ruleset. Writing rulesets needs repository admin
rights, so **`just ruleset` is a human (admin) step** — an agent never runs it.
Rerun it after editing `main.json`.

A required check must be a job that runs on every pull request and cannot be
skipped: never a job in a workflow whose `pull_request` trigger has `paths` or
`paths-ignore` (other pull requests would wait forever), and never a job whose
`if:` could skip it — a skipped required check counts as passing. A job with
`needs:` must be guarded with `!cancelled()` or `always()` and fail on its own
when a needed job failed, as `Coverage` does; it is required instead of the
test shards. `tests/test_apply_ruleset.py` enforces the trigger and `if:`
rules, and fails on a workflow layout its scanner cannot read.

### Security settings

Of the security workflows, only CodeQL (`codeql.yml`) uploads results, to code
scanning; OSV-Scanner (`osv-scanner.yml`) and gitleaks (`security-audit.yml`)
just fail the job. These are separate repository settings to turn on:

- Secret scanning, and its push protection
- Private vulnerability reporting (the route `SECURITY.md` gives)
- Dependabot alerts
- The dependency graph, which Dependency Review (`dependency-review.yml`) needs

Do not enable CodeQL "default setup": it rejects uploads from the advanced
`codeql.yml`, which fails the required "Analyze" checks.

On a private repository, CodeQL and Dependency Review need GitHub Code
Security, and secret scanning needs GitHub Secret Protection. Without them,
delete `codeql.yml` and `dependency-review.yml` rather than guarding them with
an `if:` on visibility — but first remove "Analyze (python)", "Analyze
(actions)", and "Dependency Review" from `.github/rulesets/main.json` and
re-run `just ruleset`, or every pull request waits forever on them; `osv-scanner.yml`, `security-audit.yml`, and `ci.yml`'s
zizmor job run anywhere. Private vulnerability reporting works only on public
repositories, so a private repository must replace the reporting route in
`SECURITY.md` and the security contact link in
`.github/ISSUE_TEMPLATE/config.yml` with another contact.

## Conventions: tests/**/*.py

- Mirror the source layout: `tests/<layer>/test_<module>.py` for `src/my_app/<layer>/<module>.py`, `tests/test_<module>.py` for a top-level module; use descriptive names such as `test_<what>_<scenario>_<expected_result>`.
- Test behavior through the public API, using Arrange-Act-Assert and covering both happy and error paths for each public function.
- Verify exception messages with `pytest.raises(..., match=r"...")`; also test cleanup and recovery after failures.
- Consider empty, boundary, type, collection, concurrent, and state-transition cases; use parametrization with readable ids for related inputs.
- Prefer narrow factory fixtures, `tmp_path` for filesystem work, `monkeypatch` for environment variables, and `yield` teardown for resources.
- Mock only I/O or other external boundaries; prefer fakes and assert outcomes rather than call counts, except when the call itself is the contract (retry/rate-limit behavior, a skipped step, proving no network call happened).
- Keep tests isolated and deterministic: no shared mutable state, ordering dependencies, `@pytest.mark.skip`, TODO tests, or `time.sleep()`.
- Maintain the 80% coverage floor, prioritize branch and error-path coverage, and fix flaky tests instead of suppressing them.

## Important Reminders

- All code, docs, commits, and PRs must be written in English
- Do what has been asked; nothing more, nothing less
- Note improvements you spot outside the current scope instead of making them (`triaging-issues` says how)
- NEVER create files unless absolutely necessary
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files unless explicitly requested
- Dependencies should always be added to the appropriate group in pyproject.toml

## Conventions: docs/**/*.md, README.md, CONTRIBUTING.md, CHANGELOG.md

- Document non-obvious behavior, architecture decisions, and trade-offs
- Do NOT document what is obvious from the code or already expressed by the type system
- Code examples in docs must be valid Python that works with the current API
- Use GitHub Markdown alerts (`> [!NOTE]`, `> [!WARNING]`, `> [!TIP]`) for important callouts

## Conventions: pyproject.toml

- Runtime dependencies go under `[project] dependencies`
- Dev dependencies go under `[dependency-groups] dev`
- Before adding a dependency: verify active maintenance, compatible license (MIT/BSD/Apache), and minimal transitive dependencies
- Use version ranges (`>=X.Y`) for runtime dependencies in `pyproject.toml`; `uv.lock` pins the exact versions
- NEVER remove existing ruff rules without explicit user approval
- NEVER lower the coverage threshold (currently 80%)
- After modifying dependencies, run `uv lock`, then `uv sync --all-groups --locked`
- The `uv.lock` file MUST be committed alongside dependency changes

### `[tool.uv] exclude-newer`

`exclude-newer` is a supply-chain cooldown: `uv lock` and `uv sync` ignore any
package version published after the given timestamp, so a dependency cannot be
resolved until it has survived in the wild for a while.

It is also why Python dependencies are updated **manually**, not by Dependabot:
`.github/dependabot.yml` covers GitHub Actions only. Dependencies here live in
PEP 735 `[dependency-groups]` plus `uv.lock`, which Dependabot's `pip`
ecosystem does not manage, and a bump it proposed could not be resolved past
the cutoff anyway.

Manual update procedure — run it before every release, and at least monthly
even if no dependency changed, so the cutoff does not drift too far behind:

1. Set the `exclude-newer` date in `pyproject.toml` to roughly "today minus 14 days".
2. Run `uv lock --upgrade` to move dependencies up to the new cutoff.
3. Run `just check`.
4. Commit `pyproject.toml` and `uv.lock` together in the same commit.

## Conventions: src/**/*.py, scripts/**/*.py

### Design

- Treat 300-line modules and 40-line functions as review triggers, not absolute correctness rules; split only when doing so improves a real responsibility boundary. One logical concern per module.
- Prefer 3 or fewer parameters (group related params with dataclass or TypedDict)
- Google-style docstrings (Args/Returns/Raises) on all public functions; document *why*, not what the type signature already says; don't document obvious code
- Exception: a Typer command's or a FastAPI route's docstring stays one plain-text line, because it is published as `--help` or OpenAPI text; put the reasoning in a comment or the module docstring

### Error Handling

- If the package raises more than one domain-specific error, define a package base exception and derive the others from it
- Catch the most specific exception possible
- Use `logging.exception()` in catch blocks (auto-includes traceback), never `logger.error(str(e))`
- Never swallow exceptions silently; if catching, handle meaningfully or re-raise
- Expected domain errors (`AppError`) are mapped at the entry-point boundary — an HTTP status, or an exit code plus one line on stderr — and not logged with `logging.exception()`; unexpected errors keep their traceback
- Never use exceptions for control flow
- Return `None` or a sentinel only when the caller expects it; prefer raising for true errors

### Type System

- Prefer `@dataclass(frozen=True, slots=True)` for internal value objects
- Use Pydantic (`BaseModel`) only at serialization/deserialization boundaries
- Use `TypedDict` for structured dict shapes (API responses, config dicts)
- Use `Protocol` for structural subtyping instead of ABC when possible
- Avoid `Any`; when unavoidable, add a comment explaining why (e.g., `# Any: third-party lib has no stubs`)

### Performance

Do not optimize preemptively; profile measured hotspots and note the measurement in the PR description.

### Pythonic Patterns

- EAFP (try/except) over LBYL (if-check) when dealing with duck typing or I/O
- Use context managers (`with`) for all resource management (files, connections, locks)
- Prefer comprehensions over `map()`/`filter()` for readability
- Use `enum.Enum` for fixed sets of values instead of string constants
- Use walrus operator (`:=`) for assign-and-test when it improves clarity
- Use structural pattern matching (`match/case`) for complex dispatch
- Use `*args` unpacking and `**kwargs` deliberately; avoid passing them blindly through call chains

### Security

- Sanitize file paths to prevent directory traversal (`pathlib.Path.resolve()` then check prefix)
- Ruff's bandit rules (`S`) cover eval/exec/pickle/random misuse — do not suppress them with `noqa` without a written justification

### Constants and Naming

- Use `UPPER_SNAKE_CASE` named constants instead of magic numbers/strings
- Boolean variables/params: prefix with `is_`, `has_`, `can_`, `should_`
- Private helpers: prefix with `_`; reserve `__` (name mangling) only for avoiding conflicts in subclass hierarchies

## Pre-commit layer

The guard rails run as git hooks through [pre-commit](https://pre-commit.com/)
(`.pre-commit-config.yaml`), so they hold for every author — a human, Claude
Code, Codex CLI, or any other tool. No agent-specific hook is committed.

- `check-staged` (`scripts/check_staged.py`) refuses a commit that stages a
  secret-shaped path — `.env` and `.env.*` except `.env.example`, `.envrc` and
  `.envrc.*`, anything under `secrets/`, `*.pem`, `*.key`, `id_rsa*`,
  `.claude/settings.local.json` at any depth, `.codex/rules/local.rules` — or
  a file whose staged content holds an AWS access key, a GitHub, Anthropic,
  OpenAI project, OpenRouter, Slack, or Stripe live token, or a PEM
  private-key header. It judges the index, not the working tree, names the
  file and the kind of secret, and never prints the matched value. It is
  stdlib-only and runs with pre-commit's own interpreter, so it needs no uv.
- `check-staged` runs on every `git commit` — including the one that
  concludes a conflicted merge — and on clean merges (git's `pre-merge-commit`
  hook). In a merge, content identical to what the merged-in branch already
  has at the same path is not judged again; conflict resolutions and other
  new content are. It is the only hook that runs at `pre-merge-commit`; every
  other hook runs on `git commit` only.
- Commits that git makes itself run no pre-commit hook at all: the commits
  `git rebase` replays (including after `git rebase --continue`),
  `git cherry-pick`, and `git revert`. The backstop for those is the weekly
  full-history scan of the Security Audit workflow (gitleaks).
- `just install` installs both git hooks and fails when either is missing
  afterwards. With `ALLOW_MISSING_GIT_HOOKS=1` or `CI=true` it still attempts
  the install, but a failed install or a missing hook is only a warning.
- An existing checkout installed before the `pre-merge-commit` hook existed
  has only the `pre-commit` hook: re-run `just install` to add it.
- Git hooks live in the main checkout's `.git/hooks/` and are shared by every
  linked worktree. Run `just install` from the main checkout: run from a
  worktree, it points the shared hooks at that worktree's `.venv`.

### What replaced the agent hooks

The repository used to wire agent hook scripts into Claude Code and Codex
CLI. Each behavior they had now lives here:

| Former agent hook behavior | Where it lives now |
|---|---|
| Format-on-edit (`format.py`) | An opt-in personal hook in the gitignored `.claude/settings.local.json` (snippet below) |
| Blocking `git commit --no-verify`, plain force-push, `gh pr merge --admin` (`guard.py`) | The owner's user-level deny rules, plus "never bypass a git hook" in [Security and human approval](#security-and-human-approval) |
| Blocking writes to `uv.lock` (`guard.py`) | `just verify`'s `lock-check` (`uv lock --check`) |
| Blocking writes to `.env*` and `secrets/**` (`guard.py`) | `check-staged` refuses them at commit time |
| ruff and mypy before an agent ends its turn (`stop_check.py`) | The ruff and mypy pre-commit hooks, and `just verify` |

Format-on-edit for Claude Code, in `.claude/settings.local.json` (needs `jq`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "f=$(jq -r '.tool_input.file_path // empty'); case \"$f\" in *.py) cd \"$CLAUDE_PROJECT_DIR\" && uv run --locked ruff check --fix --quiet \"$f\"; uv run --locked ruff format --quiet \"$f\" ;; esac; exit 0"
          }
        ]
      }
    ]
  }
}
```

Agent worktrees under `.claude/worktrees/` (if used) accumulate over time;
`just worktree-clean` removes the ones whose branch already has a merged PR.
