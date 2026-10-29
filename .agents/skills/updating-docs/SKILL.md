---
name: updating-docs
description: >
  Decides whether a change owes a documentation update and which surface it lands on:
  README.md (quickstart, CLI and HTTP tables, exit codes, configuration), CONTRIBUTING.md,
  AGENTS.md, a skill, or a docstring - plus what belongs in prose,
  GitHub Markdown alerts, and examples that must work with the current code. Use when
  deciding whether a pull request needs a document changed, when one change must move
  two files at once, or when a command, setting, or behavior a document describes
  changed.
---

# Updating Docs

**Owns:** whether a change owes a documentation update, which surface it lands on, and
how documentation prose is written. **Does not own:** how a skill is authored and
mirrored (`authoring-skills`); which changes are design changes
(`AGENTS.md`'s "Before changing the architecture"); the project's direction (`triaging-issues`); what a docstring says (`writing-python`); the error and
exit-code tables' content (`designing-errors`).

## Decide on what a reader can observe

Documentation impact follows what a reader can observe, not which directory the edit
began in. A command, an HTTP route, a status code, an exit code, a `MY_APP_*` setting, a
`just` recipe, or a step of setup changing is observable. An internal refactor or a
test-only change needs no documentation change — say so in the pull request rather than
leaving the reader to guess. Deciding that nothing is owed is a legitimate outcome.

A documentation file nobody asked for is never created (AGENTS.md's "Overview"); extend
the surface that already owns the topic.

## Design lives in the skills

How the app is built and why — its layers, ports, adapters, entry points, settings, and
the LLM layer — is written once, in the skill that owns the subject, so a code change
owes at most that skill (and `AGENTS.md`'s "Architecture" for a layer rule). There is no
architecture overview, decision record, design-philosophy page, or roadmap to keep in
step: never create one, and never copy a skill's design into another surface. Direction
is `AGENTS.md`'s "Product" and the open issues (`triaging-issues`).

## Purpose per file

Each surface has one job; do not let one grow a second copy of another's content.

| File | Holds | Changes when |
|---|---|---|
| `README.md` | What the application does, the quickstart, the CLI and HTTP table, error statuses and exit codes, the configuration table, the repository layout | A command, route, status, exit code, setting, or top-level module it documents changes |
| `CONTRIBUTING.md` | Prerequisites, setup, the development commands, the pull request process, commit messages | Setup, the toolchain, or the pull request process changes |
| `AGENTS.md` | What every agent task needs: the quick reference, the "Validating a change" table, the layer rules, the Product section, the Skills table, the approval rules, the enforcement layers | One of those facts changes |
| `.agents/skills/<name>/` | One kind of change's conventions, and the design of the subject it owns with its reasons, loaded on demand | Those conventions or that design change (`authoring-skills`) |
| Docstrings | A function's contract and its why | The function changes (`writing-python`) |

<!-- template-only -->
In the template, `TEMPLATE.md` says only how to use the template; the reasons behind
its design live in the owning skills, like an app's. `scripts/bootstrap.py` deletes it
from an app.
<!-- /template-only -->

`README.md` links to `CONTRIBUTING.md` and `AGENTS.md` instead of repeating them, so it
must not grow a second command index or a second rule list. Merged pull requests and
closed issues record shipped changes; `git log` shows the local history.

## Changes that move two files at once

Some facts have two readers, and a pull request that changes one copy owes the other.
Where the last column names a test, a miss fails the suite; "review" means only the
reader of the diff catches it.

| When you change | Also change | Caught by |
|---|---|---|
| A skill added, renamed, or deleted | Its row in AGENTS.md's Skills table | `tests/harness/test_skills.py` (`just check-harness`) |
| A `just` recipe added, renamed, or removed | Its line in AGENTS.md's "Quick Reference", in the block for who runs it; `CONTRIBUTING.md` if it lists the recipe | `tests/harness/test_just_recipes.py` when a document it reads still names a renamed or removed one (its docstring lists them; not `docs/product/` or `.devcontainer/`); review for an added one |
| A gate, or the narrowest check for one kind of change | Its row in AGENTS.md's "Validating a change" | review |
| A CLI command or an HTTP route | `README.md`'s command table | review |
| A `MY_APP_*` setting | `README.md`'s configuration table | review |
| An `AppError` mapping or an exit code | `README.md`'s error text and exit-code table | `tests/cli/test_errors.py` pins the codes |
| A label in `.github/labels.yml` | `.github/workflows/pr-label.yml`'s mapping, if it names it | `tests/harness/test_labels.py` |
| A required CI job | `.github/rulesets/main.json` | `tests/harness/test_ruleset_contexts.py`; `tests/test_apply_ruleset.py` pins the list |

**BACKGROUND:** `smart-commit` for the pairs that must share a commit, not only a pull
request. Adding a script reaches more files; **REQUIRED:** `writing-repo-scripts`.

## What belongs in prose

- Document non-obvious behavior, design decisions, and trade-offs; a design decision
  goes in the skill that owns its subject.
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
a command must run as written. No gate compiles or runs a fenced block or checks that a
named path still exists. `just check-harness` checks a `just <recipe>` in command
position, but not in `docs/product/` or `.devcontainer/`. Check
by hand before committing:

- every `just <recipe>` you name appears in `just --list`;
- every file path you name exists;
- every Python example imports from the module that defines the name today.

Keep a fenced example to something a reader can check by eye — a command, a request
body, a path. When an example has to be runnable, put it in a test and point at the
test rather than copying it.

## Generated trees are off-limits

`.claude/skills/` is a generated mirror of `.agents/skills/` (`just agents-sync`):
never hand-edit it, and never include it in a documentation sweep.
