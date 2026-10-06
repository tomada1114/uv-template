# Project Guide

## Overview

This is a Python library built with [uv](https://docs.astral.sh/uv/) and
[hatchling](https://hatch.pypa.io/). It uses a strict `src/` layout with
comprehensive type checking and linting.

## Quick Reference

```bash
just install         # Install dependencies and git hooks when .git/ is present
just setup           # Alias for just install (first-time setup)
just fmt             # Format code (ruff check --fix + ruff format)
just lint            # Lint (ruff check) + type check (mypy)
just test            # Run tests in parallel with coverage
just test-durations  # Regenerate the pytest-split duration file used by CI shards
just smoke           # Build and verify wheel and sdist in temp environments
just check           # Mutating dev check: fmt → lint → test
just lock            # Update uv.lock after dependency changes
just verify          # Non-mutating gate: lock-check → agents-check → lint → test-skills → docs → smoke → test
just test-skills     # Run the unittest suites bundled under .agents/skills/*/scripts/tests
just docs            # Serve docs locally
just docs-check      # Build docs and fail on warnings
just build           # Build distribution packages
just worktree-clean  # Remove agent worktrees under .claude/worktrees with a merged PR
just agents-sync     # Regenerate the .claude/skills mirror from .agents/skills
just agents-check    # Fail when the skills mirror has drifted
just labels          # Create/update GitHub labels from .github/labels.yml (writes to GitHub; ask first)
just clean           # Remove build artifacts and caches
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
| A module under `src/` | `uv run --locked pytest tests/test_<module>.py` |
| One test | `uv run --locked pytest tests/test_<module>.py::test_<name>` |
| Any Python file's lint or types | `uv run --locked ruff check <file>`, then `uv run --locked mypy src scripts tests` |
| A script under `scripts/` | `uv run --locked pytest tests/test_<script>.py` |
| A skill under `.agents/skills/` | `just agents-sync && just agents-check && just test-skills` |
| Dependencies in `pyproject.toml` | `uv lock`, `uv sync --all-groups --locked`, then `just verify` |
| `docs/` or `mkdocs.yml` | `just docs-check` |
| A workflow under `.github/workflows/` | `uv run --locked pre-commit run zizmor --all-files` |
| Markdown or other prose | `uv run --locked pre-commit run typos --files <file>` |

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

## Sources of Truth

| Concern | Canonical source |
|---|---|
| Tooling and quality commands | `justfile`, `pyproject.toml`, CI workflows |
| Current public API shape | `src/my_package/__init__.py` `__all__` and public signatures |
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
| `create-pr` | opening or updating a pull request |
| `merging-dependency-prs` | landing open Dependabot pull requests (GitHub Actions bumps) |
| `release-workflow` | cutting a release |
| `shipping-issues` | shipping the next issue or the whole backlog: rank, implement, review, PR, CI, merge |
| `smart-commit` | grouping working-tree changes into commits |
| `triaging-issues` | filing, labelling, or prioritizing an issue, or recording a problem found outside the task |

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

1. `just verify` passes (lock check, lint, strict docs build, wheel/sdist smoke, tests)
2. New public APIs have type annotations and docstrings
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
  The `guard.py` hook (see "Agent hooks") blocks the most dangerous spellings,
  but its inspection is best-effort; this instruction is the rule itself.
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

## Conventions: tests/**/*.py

- Mirror the source layout with `tests/test_<module>.py`; use descriptive names such as `test_<what>_<scenario>_<expected_result>`.
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
- Use admonitions (note, warning, tip) for important callouts in MkDocs pages

## Conventions: pyproject.toml

- Runtime dependencies go under `[project] dependencies`
- Dev dependencies go under `[dependency-groups] dev`; docs under `[dependency-groups] docs`
- Before adding a dependency: verify active maintenance, compatible license (MIT/BSD/Apache), and minimal transitive dependencies
- Use version ranges (`>=X.Y`) for runtime dependencies -- never pin exact versions in a library
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

### Error Handling

- If the package raises more than one domain-specific error, define a package base exception and derive the others from it
- Catch the most specific exception possible
- Use `logging.exception()` in catch blocks (auto-includes traceback), never `logger.error(str(e))`
- Never swallow exceptions silently; if catching, handle meaningfully or re-raise
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

## Agent hooks

The project hook configuration runs the scripts in `.agents/hooks/` for tool
calls made in this repository. The wiring files are `.claude/settings.json`
(which holds nothing but this wiring) and `.codex/hooks.json`.

- `guard.py` (PreToolUse) blocks writes to `uv.lock`, `.env*`, and `secrets/**`,
  plus `git commit --no-verify`, plain force-pushes, and `gh pr merge --admin`.
- `format.py` (PostToolUse) runs ruff fixes and formatting on edited Python files.
- `stop_check.py` (Stop) runs ruff and mypy when Python files or `pyproject.toml` changed.

`.claude/settings.json` uses `${CLAUDE_PROJECT_DIR}` because it remains stable when multiple repositories are open; `.codex/hooks.json` uses `$(git rev-parse --show-toplevel)` because Codex has no `CLAUDE_PROJECT_DIR`.

Start sessions from the repository root so project-level hook configuration is loaded; review and trust each hook before relying on it.
Agent worktrees under `.claude/worktrees/` (if used) accumulate over time;
`just worktree-clean` removes the ones whose branch already has a merged PR.
