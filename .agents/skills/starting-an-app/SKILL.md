---
name: starting-an-app
description: >
  Covers turning this template into a new app and its first steps: scripts/bootstrap.py
  (flags, refusals, .template-origin, its CI smoke job), AGENTS.md's Product section
  and tests/test_product_section.py, the roadmap, keeping the HTTP API, the CLI, or
  both, removing the sample to-do domain, the first ADRs (app shape, persistence), just
  labels, just ruleset, GitHub security settings, secrets, and a private repository.
  Use when starting an app from this repository, running or changing the bootstrap, a
  placeholder survived the rename, or setting up the new repository.
---

# Starting an App

**Owns:** the order of work from "Use this template" to an app's first feature: the
rename, the Product section and roadmap as steps, the app's shape, removing the sample,
the first ADRs, and the new repository's GitHub setup. **Does not own:** what the
roadmap says (`steering-the-roadmap`); how an ADR is written
(`recording-architecture-decisions`); labels and issue bodies (`triaging-issues`); the
list of GitHub settings and why each matters (`AGENTS.md`'s "GitHub settings a new
repository must enable"); which files go with each entry point (`AGENTS.md`'s
"Architecture").

Steps marked **human** are a person's: an agent never runs them, and only drafts or
lists them for the owner. Steps that write to GitHub run only with the owner's sign-off
(`AGENTS.md`'s "Security and human approval").

## The order

1. **Create and clone.** "Use this template" on GitHub (the user-level
   `bootstrapping-from-templates` skill does this and drives the steps below), clone
   the new repository, then `just install`.
2. **Rename.** `scripts/bootstrap.py` renames the template into the app, records the
   template commit it was cut from in `.template-origin`, and deletes itself, so in an
   app this step is already done.
   <!-- template-only -->
   It rewrites the whole repository, so run it only on the owner's request, on a fresh
   clone with a clean work tree. **REQUIRED:**
   [references/bootstrap.md](references/bootstrap.md), for its flags, what it refuses,
   and what it removes, before running it, changing it, or chasing a leftover
   placeholder.
   <!-- /template-only -->
3. **Commit the rewrite** as one commit, before editing anything, so the rename stays
   one reviewable diff: review `git status` and `git diff` first.
4. **Write `AGENTS.md`'s Product section**: what the app is and for whom, the core
   interaction, the non-goals, and where those decisions are recorded
   (`docs/product/requirements.md`). The owner decides every entry; an agent drafts one
   only from what the owner has said. `tests/test_product_section.py`, and so
   `just verify`, fails while a `TODO:` is left there. Write it before any feature: a
   non-goal nobody wrote down is one an eager implementer reads as a feature.
5. **Fill `docs/architecture/roadmap.md`** with the Now, Next, and Later outcomes that
   follow from the Product section, per `steering-the-roadmap`.
6. **Verify and push.** `just verify`, commit the Product section and roadmap, and push
   to `main`, which takes a direct push until step 10's ruleset exists. Pushing is a
   remote write.
7. **Labels.** `just labels` creates `.github/labels.yml`'s labels on the new
   repository (`triaging-issues`). Run it before the first issue is filed: an issue
   form or a planning tool applying a missing label loses it silently. It writes to
   GitHub.
8. **Security settings and secrets** (**human**, the repository's admin): turn on what
   `AGENTS.md`'s "GitHub settings a new repository must enable" › "Security settings"
   lists. The template's workflows need no secret beyond the `GITHUB_TOKEN` GitHub
   provides; a secret the app adds later (a deploy key, an API key) is set by a person
   in the repository's settings and never committed — `check-staged` refuses one.
9. **Replace the sample**, in the order of the sections below: the app's shape, the
   first ADRs, then the to-do domain.
10. **Ruleset, last** (**human**, an admin): `just ruleset` applies
    `.github/rulesets/main.json`. From then on every change needs a pull request with
    the required checks green, so the ruleset must name only jobs the app still runs.
    On a **private repository**, first **REQUIRED:**
    [references/private-repository.md](references/private-repository.md).

## Choose the app's shape

The template ships both entry points over one framework-free core: the FastAPI HTTP
API and the Typer CLI. Decide which the app needs before its first feature, and write
the answer into the Product section's core interaction:

- **Both**, when people use it at a terminal and other programs call it over HTTP.
- **API only**, for a service. **CLI only**, for a tool run by hand or by a scheduler.

Dropping an entry point is a list of deletions, never a core change: `AGENTS.md`'s
"Architecture" names every file, dependency, recipe, and ruff entry that goes with
each, and README's "Architecture" holds the same list for readers. Run `uv lock` after
removing a dependency, then `just verify`.

## Record the first ADRs

Write each as Proposed (only the owner accepts), in `docs/architecture/adr/` with its
row in `docs/architecture/README.md`, per **REQUIRED:**
`recording-architecture-decisions`:

- **App shape**: which entry points the app keeps, and why the other went.
- **Persistence**: where and in what format the app keeps state — the in-memory
  repository, the stdlib SQLite adapter, or another store — with how a schema change
  reaches existing data. Write it as soon as the app keeps state of its own.

Each new runtime dependency or external service the first features need is an ADR too,
and a new dependency waits for the owner's sign-off.

## Remove the sample to-do domain

The to-do list is a deletable illustration, not the app. Replace it in the same pull
request that removes it, so the tests and the 80% coverage floor still measure real
code:

- the domain in `src/my_app/core/` (`models.py`, `ports.py`, `services.py`, and the
  `TodoNotFoundError`/`InvalidTodoError` in `errors.py`), and the adapters in
  `src/my_app/adapters/` that implement its repository port;
- the entry points' wrappers: `src/my_app/api/routers/todos.py` and the to-do models
  in `api/schemas.py`, and `src/my_app/cli/todo.py` with its registration in
  `cli/main.py`;
- their tests under `tests/core/`, `tests/adapters/`, `tests/api/`, and `tests/cli/`,
  and the contract suite's parameters in `tests/adapters/test_repository_contract.py`;
- README's Quickstart, the CLI/HTTP table, and the Configuration section, the `just run`
  example in the `justfile`, and the command line in
  `.github/ISSUE_TEMPLATE/bug_report.yml`.

Keep what is general: `core.errors.AppError` and the one place each entry point maps it
(the API's handler in `api/app.py`, the CLI's exit codes in `cli/errors.py`), the
composition root, `settings.py` and its environment prefix, the health route, the
banned-api lint rule that keeps the core framework-free, and `tests/conftest.py`'s fixed
clock. Then search the tree for `Todo`, `todo`, and `to-do`, and judge each hit: an app
whose own name holds one of them keeps those.

## What the new app keeps

Everything about the repository rather than the application survives unchanged: the
`justfile`, every workflow except the template's own bootstrap job, the pre-commit layer
and its secret gate, the skills and sub-agent tiers (drop a skill only when its subject
leaves the repository, with its row in `AGENTS.md`'s Skills table), the label set, and
the ruleset. A red check early in a new app is an argument for fixing the code, never
for deleting or weakening the check.
