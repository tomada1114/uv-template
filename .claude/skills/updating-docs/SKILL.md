---
name: updating-docs
description: >
  Decides whether a change owes a documentation update and which surface it lands on:
  README.md (quickstart, CLI and HTTP tables, exit codes, configuration), CONTRIBUTING.md,
  CHANGELOG.md's [Unreleased] entry, AGENTS.md, a skill, docs/architecture/, TEMPLATE.md,
  or a docstring - plus what belongs in prose, GitHub Markdown alerts, and examples that
  must work with the current code. Use when deciding whether a pull request needs a
  document changed, when one change must move two files at once, or when a command,
  setting, or behavior a document describes changed.
---

# Updating Docs

**Owns:** whether a change owes a documentation update, which surface it lands on, and
how documentation prose is written. **Does not own:** how a skill is authored and
mirrored (`authoring-skills`); an ADR or the roadmap (`recording-architecture-decisions`,
`steering-the-roadmap`); what a docstring says (`writing-python`); the error and
exit-code tables' content (`designing-errors`).

## Decide on what a reader can observe

Documentation impact follows what a reader can observe, not which directory the edit
began in. A command, an HTTP route, a status code, an exit code, a `MY_APP_*` setting, a
`just` recipe, or a step of setup changing is observable. An internal refactor or a
test-only change needs no documentation change — say so in the pull request rather than
leaving the reader to guess. Deciding that nothing is owed is a legitimate outcome.

Create no new documentation file unless the request asks for one; extend the surface
that already owns the topic.

## Purpose per file

Each surface has one job; do not let one grow a second copy of another's content.

| File | Holds | Changes when |
|---|---|---|
| `README.md` | What the application does, the quickstart, the CLI and HTTP table, error statuses and exit codes, the configuration table, dropping an entry point | A command, route, status, exit code, or setting it documents changes |
| `CONTRIBUTING.md` | Prerequisites, setup, the development commands, the pull request process, commit messages, the changelog policy | Setup, the toolchain, or the pull request process changes |
| `CHANGELOG.md` | Keep a Changelog; an entry under `[Unreleased]` | Any user-facing change, in the same pull request |
| `AGENTS.md` | What every agent task needs: the quick reference, the "Validating a change" table, the architecture, the Skills table, the approval rules, the enforcement layers | One of those facts changes |
| `.agents/skills/<name>/` | One kind of change's conventions, loaded on demand | Those conventions change (`authoring-skills`) |
| `docs/architecture/` | ADRs and the roadmap | A decision owes an ADR, or the direction moves |
| `TEMPLATE.md` | Why the template is built this way and how to bootstrap it; `scripts/bootstrap.py` deletes it | The template's design or bootstrap changes |
| Docstrings | A function's contract and its why | The function changes (`writing-python`) |

`README.md` links to `CONTRIBUTING.md` and `AGENTS.md` instead of repeating them, so it
must not grow a second command index or a second rule list. A `CHANGELOG.md` entry says
what a user notices, not which files moved.

## Changes that move two files at once

Some facts have two readers, and a pull request that changes one copy owes the other.
Where the last column names a test, a miss fails the suite; "review" means only the
reader of the diff catches it.

| When you change | Also change | Caught by |
|---|---|---|
| A skill added, renamed, or deleted | Its row in AGENTS.md's Skills table | review |
| A `just` recipe added, renamed, or removed | Its line in AGENTS.md's "Quick Reference", in the block for who runs it; `CONTRIBUTING.md` if it lists the recipe | review |
| A gate, or the narrowest check for one kind of change | Its row in AGENTS.md's "Validating a change" | review |
| A CLI command or an HTTP route | `README.md`'s command table | review |
| A `MY_APP_*` setting | `README.md`'s configuration table | review |
| An `AppError` mapping or an exit code | `README.md`'s error text and exit-code table | `tests/cli/test_errors.py` pins the codes |
| A label in `.github/labels.yml` | `.github/workflows/pr-label.yml`'s mapping, if it names it | `tests/test_sync_labels.py` |
| A required CI job | `.github/rulesets/main.json` | `tests/test_apply_ruleset.py` |

**BACKGROUND:** `smart-commit` for the pairs that must share a commit, not only a pull
request. Adding a script reaches more files; **REQUIRED:** `writing-repo-scripts`.

## What belongs in prose

- Document non-obvious behavior, architecture decisions, and trade-offs.
- Do not document what is obvious from the code or already expressed by the type
  system. If a reader could get the fact from the signature or by running the code, it
  needs no sentence.
- Use GitHub Markdown alerts (`> [!NOTE]`, `> [!WARNING]`, `> [!TIP]`) for an important
  callout, as `README.md`'s configuration note does.
- Write a fact about an external tool with its source and the date it was checked, or
  as an observation with the command that showed it (`authoring-skills`' "External
  claims").

## Examples must work

A code example in a document must be valid Python that works with the current code, and
a command must run as written. No gate compiles or runs a fenced block, and none checks
that a named recipe or path still exists, so check by hand before committing:

- every `just <recipe>` you name appears in `just --list`;
- every file path you name exists;
- every Python example imports from the module that defines the name today.

Keep a fenced example to something a reader can check by eye — a command, a request
body, a path. When an example has to be runnable, put it in a test and point at the
test rather than copying it.

## Generated trees are off-limits

`.claude/skills/` is a generated mirror of `.agents/skills/` (`just agents-sync`):
never hand-edit it, and never include it in a documentation sweep.
