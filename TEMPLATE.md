# About This Template

This file documents the template itself: why it is built the way it is, and
how to turn a copy of it into a real application. `scripts/bootstrap.py` deletes
it from the spawned repo, so nothing here ships with your application.

## Using This Template

1. Click **"Use this template"** on GitHub (or clone and remove `.git`)
2. Run `scripts/bootstrap.py` to rename the package and replace placeholders:

   ```bash
   uv run --locked python scripts/bootstrap.py my-cool-lib \
     --author "Jane Doe" --email jane@example.com --github-user janedoe \
     --github-repository my-cool-lib-repo \
     --description "One line about what this application does."
   ```

   This renames `src/my_package` to `src/my_cool_lib` and replaces
   `my-package`, `my_package`, `uv-template`, `your-username`, `Your Name`,
   and `you@example.com` across all eligible tracked files. The distribution name and
   GitHub repository name may differ; omit `--github-repository` when they are
   the same. Metadata values are validated before any files are changed, and
   quoted author and description values are escaped for TOML. The
   script also writes the current year into `LICENSE`, moves `[tool.uv]
   exclude-newer` to two weeks before today, resets `CHANGELOG.md` to an empty
   skeleton, and runs `uv lock` (a lock file still naming the template would
   fail the first CI run — if the lock step warns, run `uv lock` yourself
   before committing).

   `--github-user` is required: it is baked into the project URLs, and
   leaving it out ships a dead security-report link in
   `.github/ISSUE_TEMPLATE/config.yml`. `--author`, `--email`, and
   `--description` are optional; any omitted placeholder is left as-is.

   Finally the script deletes its own scaffolding — this file,
   `scripts/bootstrap.py`, and `tests/test_bootstrap.py`. Pass
   `--keep-bootstrap` to keep them.
3. Update `pyproject.toml` metadata (keywords, URLs) beyond what the
   script covers
4. Update `README.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, and
   `AGENTS.md`; update `CLAUDE.md` only when the new project has
   Claude-specific settings or workflow notes
5. Replace the placeholder implementation and keep the README usage examples
   in sync with it

To find any placeholders the script left untouched (e.g. because an
optional argument was omitted):

```bash
rg -n "your-username|my-package|my_package|uv-template|Your Name|you@example" .
```

### Working in the new repository

- **Never commit directly on `main`.** The pre-commit `no-commit-to-branch`
  hook blocks it, and `--no-verify` would also switch off the secret gate
  (`scripts/check_staged.py`), so the way through is a feature branch and a
  PR — not a bypass flag.
- The toolchain baseline is Python 3.14 (`requires-python`, ruff
  `target-version`, mypy `python_version`, `.python-version`, the
  devcontainer image, and every CI workflow). Lower it everywhere at once if
  the new project needs to support older interpreters.
- Python dependencies are updated manually; see
  the `pyproject.toml` convention in `AGENTS.md` for the `exclude-newer`
  procedure.
- `just verify` (lock check, skills mirror, lint, skill tests, tests) is the
  non-mutating gate for a PR or a completion claim; `just check` mutates the
  tree first (`fmt`) and is for local iteration only.

## Design Philosophy

Every choice in this template has a reason. If you disagree with a decision,
you know exactly what to change and why it was there in the first place.

### Why `src/` layout?

The `src/` layout prevents accidental imports of the local package during
development and testing. It ensures that tests always run against the
*installed* package rather than the working tree, so a missing module or a
broken package configuration fails the test run instead of the deployed app.

### Why strict mypy + comprehensive Ruff rules?

Type errors and lint issues are cheapest to fix at write time. Strict settings
from day one mean every line of code is held to the same standard — there is
never a "legacy" codebase to clean up. LLMs generating code also benefit from
strict rules: they produce higher-quality output when constraints are clear.

### Why zero runtime dependencies?

The template should not impose opinions about logging, HTTP clients, or data
validation. You add what your application needs. Starting from zero keeps the
dependency tree small and every dependency a deliberate choice.

### Why Just over Make?

Just has cleaner syntax (no mandatory tabs), better cross-platform support, and
more readable recipe definitions. It is a task runner, not a build system —
which is exactly what a Python project needs.

### Why AGENTS.md and the agent configuration?

AI-assisted development is the norm, not the exception. `AGENTS.md` gives any
coding agent (Claude Code, Codex, Cursor, Gemini CLI, ...) the context it
needs to match your project's standards; `CLAUDE.md` imports it and adds
Claude Code specifics. Skills are authored once in `.agents/skills/` and
mirrored into `.claude/skills/` (`just agents-sync`); `.claude/agents/` and
`.codex/agents/` define the same three sub-agent tiers for each host.
Permission allowlists, model choices, plugin marketplaces, and editor hooks
are personal and are never committed.

### Why a pre-commit layer instead of agent hooks?

A guard rail wired into one agent's hook configuration protects nothing when
a human, or a different tool, makes the commit. So the template commits no
agent hooks: its guard rails are git hooks run by pre-commit, which fire on
`git commit` for every author. `scripts/check_staged.py` refuses secret-shaped
paths and credential-shaped content straight from the index, on every
`git commit` and every merge commit, and `just install` fails when the git
hooks are missing. Commits git makes without running hooks — `git rebase`
replays, `git cherry-pick`, `git revert` — are left to the weekly full-history
scan of the Security Audit workflow (gitleaks). What the old agent hooks did and where each behavior went is the
replacement table under "Pre-commit layer" in `AGENTS.md`.

### Why 80% coverage minimum?

80% is high enough to catch most regressions but low enough to avoid
test-for-the-sake-of-testing. Branch coverage is enabled, so conditional logic
is meaningfully tested.
