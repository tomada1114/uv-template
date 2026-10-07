# Project Guide

## Overview

A Python application built with [uv](https://docs.astral.sh/uv/) and
[hatchling](https://hatch.pypa.io/), in a strict `src/` layout with comprehensive
type checking and linting. A framework-free core carries two entry points: a
FastAPI HTTP API and a Typer CLI (`my-app`). The sample domain is a to-do list —
replace it with your own, and delete whichever entry point you do not need.

Every task here:

- Write everything — code, docs, commits, pull requests — in English.
- Do what has been asked; nothing more, nothing less. Note an improvement
  outside the current scope instead of making it (`triaging-issues`).
- Create no file unless it is absolutely necessary, and no documentation file
  unless asked; prefer editing an existing one.

## Product

<!-- template-only -->
In the template every entry below stays a `TODO:` on purpose: each repository cut
from it writes its own, and `tests/test_product_section.py` fails here if one is
filled in.
<!-- /template-only -->

This section is about the application rather than the harness: without it, an
agent implementing an issue has no in-repo answer to "is this in scope?". The owner
decides every entry; an agent drafts one only from what the owner has said. Once the
bootstrap has run (`.template-origin` exists), `tests/test_product_section.py` — and
so `just verify` — fails while any entry below is still a placeholder.

- **What it is, and who it is for** — TODO: one paragraph: the problem it solves,
  and whose problem that is.
- **The core interaction** — TODO: the one thing a user does most. If the app does
  not do this well, nothing else about it matters.
- **Non-goals** — TODO: what this app deliberately does not do, even where it would
  be easy. Moving anything from here to a goal is a human's decision, not an
  implementer's.
- **Where these decisions are recorded** — TODO: `docs/product/requirements.md`,
  and the ADRs under `docs/architecture/` for the choices made since.

## Quick Reference

Grouped by who runs them; the `justfile` is the source of truth, this its index.

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

`just dev` is the developer's server: never start, stop, or restart it, or bind
its port. To see what only a running server shows, prefer a `TestClient` test,
else your own `my-app serve` on a free port, stopped before your turn ends
(`running-the-app`).

### Writes to GitHub

```bash
just labels          # Create/update GitHub labels from .github/labels.yml (ask first)
just ruleset         # Apply .github/rulesets/main.json to GitHub (admin-only human step; never an agent)
```

Without Just, run the `uv run` commands the `justfile` gives each recipe.
`just check` runs `fmt` first, so it never proves the *committed* tree green;
`just verify` mutates nothing and is the gate for a PR or a completion claim.

## Validating a change

Run the narrowest check that can fail while iterating, then `just verify` before
a completion claim on any code change — on every edit it is slow enough to stop
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

The state of the work comes from Git, fresh test output, and CI — never from
prose or a test count in a prompt.

## Architecture

```
src/my_app/
├── core/            # Framework-free: domain model, ports (Protocols), services, errors
├── adapters/        # Port implementations: in-memory and SQLite (stdlib sqlite3) repositories
├── api/             # FastAPI: create_app(settings) factory, routers (api/routers/), Pydantic schemas
├── cli/             # Typer: `my-app todo add|list|complete|delete`; serve.py holds `my-app serve`
├── settings.py      # pydantic-settings `Settings`, read from MY_APP_* environment variables
└── composition.py   # Composition root: wires adapters into services for both entry points
```

- Dependencies point inward: `api/` and `cli/` call `core/` services and get
  them only from `composition.build_container`; `adapters/` implement
  `core/ports.py`; `core/` imports nothing outside the stdlib and itself.
  Ruff's `TID251` banned-api rule and `tests/core/test_imports.py` fail the
  build otherwise (`designing-core-logic`).
- Domain errors derive from `core.errors.AppError`; each entry point maps them
  in one place (`api/app.py`, `cli/errors.py`), per `designing-errors`.
- The CLI never imports the API at import time: `cli/serve.py` is the only
  bridge, and it imports FastAPI and uvicorn inside the command.
- Removing an entry point is a deletion, never a core change:
  `building-api-routes` and `designing-clis` each list what goes with theirs.

## Skills

Skills are authored under `.agents/skills/` (Codex CLI) and mirrored into
`.claude/skills/` (Claude Code): edit only `.agents/skills/`, run
`just agents-sync`, and commit both trees (`authoring-skills`).

| Skill | Load it when |
|---|---|
| `authoring-skills` | adding, editing, or reviewing a skill under `.agents/skills/`, or a skill never fires |
| `building-api-routes` | adding or changing an HTTP route, request or response model, or API dependency, and the TestClient tests for it |
| `changing-gates` | editing a hook, a CI workflow, the ruleset, or a ruff, mypy, pytest, or coverage setting, or asking whether a change weakens a gate |
| `create-pr` | opening or updating a pull request by hand |
| `designing-clis` | adding or changing a `my-app` command, its arguments, or its output, and the CliRunner tests for it |
| `designing-core-logic` | adding a use case, domain rule, port, adapter, or `MY_APP_*` setting, or wiring the composition root |
| `designing-errors` | adding a failure mode, or choosing the HTTP status or exit code a domain error becomes |
| `managing-dependencies` | adding, bumping, or removing a package, or moving the `exclude-newer` cutoff |
| `merging-dependency-prs` | landing open Dependabot pull requests (GitHub Actions bumps) |
| `placing-tests` | adding a test file or a fixture, running one test, or a coverage run below the floor |
| `recording-architecture-decisions` | a change owes an ADR, or an ADR under `docs/architecture/` is proposed, accepted, or superseded |
| `running-the-app` | running the CLI or a server of your own to observe a change, and stopping that server afterwards |
| `shipping-issues` | shipping the next issue or the whole backlog: rank, implement, review, PR, CI, merge |
| `smart-commit` | grouping working-tree changes into commits, or a pre-commit hook refuses a commit |
| `starting-an-app` | setting up an app cut from this template: the Product section, the bootstrap pull request, labels, ruleset, security settings, dropping an entry point or the sample domain, the first ADRs; in the template, the bootstrap itself |
| `steering-the-roadmap` | asked what to work on next, or the Now / Next / Later roadmap moves |
| `tdd` | changing behavior under `src/` or `scripts/`, or fixing a bug: the failing test comes first |
| `triaging-issues` | filing, labelling, or prioritizing an issue, or recording a problem found outside the task |
| `updating-docs` | deciding whether a change owes a README, CHANGELOG, AGENTS.md, or other document update |
| `writing-python` | writing or reviewing any Python module, class, or function: typing, imports, docstrings, idioms |
| `writing-repo-scripts` | adding or editing a script under `scripts/`, its `just` recipe, or its tests |
| `writing-tests` | writing or reviewing a test: its name, assertions, fixtures, fakes, and edge cases |

## Sub-agents

A skill runs every step inline by default. On a host that can hand a step to a
named sub-agent, a step marked for a tier may go to one of three:

| Tier | Effort | Takes |
|---|---|---|
| `executor` | low | a settled spec with a clear pass/fail: implementing it, adding tests, getting a check green, bulk edits, research that only collects |
| `architect` | high | design judgment, review and bug finding, multi-file work, synthesis, a spec that still has holes |
| `worker` | medium | single-shot, tool-free writing or checking from a complete brief |

Both hosts define the same three: `.claude/agents/<tier>.md` pins a model alias
(`opus`, or `sonnet` for `worker` — never a dated model ID) and an `effort`;
`.codex/agents/<tier>.toml` sets only `model_reasoning_effort`, so the session's
model is inherited. `tests/test_agent_tiers.py` holds their instructions equal.

- Neither file declares a permission — no `sandbox_mode`, no tool list.
- Codex CLI loads `.codex/` only for a trusted project (in an untrusted
  checkout a step marked for a tier runs inline), and `.codex/agents/worker.toml`
  replaces Codex's built-in `worker` inside this repository on purpose.

## Security and human approval

- **Commit, push, and pull request need a human's sign-off** — given per
  request, or by one of the [standing exceptions](#standing-exceptions) below.
  The ruleset blocks a force-push to or deletion of `main` only once a human has
  applied it with `just ruleset`; nothing else blocks a force-push or
  `gh pr merge --admin`, so this instruction is the rule itself.
- Never bypass a git hook — no `--no-verify`, no `SKIP=<hook id>`, no edit to
  `.git/hooks/`. `--no-verify` switches off the secret gate of the
  [enforcement layers](#enforcement-layers) along with everything else.
- Never weaken a gate to make a run pass: no lowered coverage threshold, no
  removed ruff rule, no `noqa`, `type: ignore`, or per-file ignore without a
  written reason, no skipped or deleted test, no removed `--locked`. If a gate
  is wrong, say so and let a human decide. `changing-gates` lists every form
  this takes.
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
  `gh pr edit` on its own open pull request — never a force-push or a merge.
- `smart-commit`: the commits it makes on the current branch, and pushing that
  branch only when asked — never a force-push and never `main`.

One request is a standing exception too: the owner explicitly asking for an
issue ("file an issue for this") signs off the `gh issue create` of each issue it
asks for, with the labels `triaging-issues` gives it. An issue the agent would
file on its own initiative is drafted in the reply and waits for a yes.

None of them covers a force-push or other history rewrite, `--no-verify` or
any other hook bypass, weakening a gate, or adding a dependency — a new
dependency is proposed and the agent stops for sign-off.

## Enforcement layers

Each layer catches what the one before it cannot; `changing-gates` owns them.

| Layer | Runs | Holds |
|---|---|---|
| Git hooks (pre-commit, `.pre-commit-config.yaml`) | Every `git commit` by any author — a human, Claude Code, Codex CLI, any tool; `check-staged` also on merge commits | No staged secret (`check-staged`), no commit on `main` (`no-commit-to-branch`), ruff, ruff-format, mypy, typos, zizmor, the skills mirror |
| `just verify` | Before a pull request or a completion claim | A current `uv.lock`, the skills mirror, ruff, mypy, the skill script tests, the test suite and its 80% branch-coverage floor |
| CI (`.github/workflows/`) | Every pull request and push to `main`, unless noted | The `just verify` checks, typos, zizmor, and CodeQL; the PR title and Dependency Review (pull requests only); OSV-Scanner (when `uv.lock` changes, and weekly); gitleaks over the whole history (weekly) |
| GitHub ruleset (`.github/rulesets/main.json`) | Every change to `main` | Every change arrives by a branch and a pull request, with the required checks green; no force-push, no deletion |

- How `just install` installs the hooks, and which commits run none:
  `changing-gates`' `references/pre-commit-layer.md`.
- No agent-specific hook, permission rule, model choice, or plugin marketplace
  is committed: one person's trust would bind every repository made from this
  template. Keep them in `~/.claude/settings.json`, `~/.codex/config.toml`, or
  the gitignored `.claude/settings.local.json` and `.codex/rules/local.rules`.
- Only a human changes the live ruleset (`just ruleset`, an admin step) or the
  repository's security settings; `starting-an-app` lists what a new one enables.
