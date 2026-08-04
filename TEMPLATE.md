# About This Template

This file documents the template itself: why it is built the way it is, and
how to turn a copy of it into a real library. `scripts/bootstrap.py` deletes
it from the spawned repo, so nothing here ships to your library's users.

## Using This Template

1. Click **"Use this template"** on GitHub (or clone and remove `.git`)
2. Run `scripts/bootstrap.py` to rename the package and replace placeholders:

   ```bash
   uv run python scripts/bootstrap.py my-cool-lib \
     --author "Jane Doe" --email jane@example.com --github-user janedoe \
     --description "One line about what this library does."
   ```

   This renames `src/my_package` to `src/my_cool_lib` and replaces
   `my-package`, `my_package`, `uv-template`, `your-username`, `Your Name`,
   and `you@example.com` across all tracked files. It also writes the current
   year into `LICENSE`, moves `[tool.uv] exclude-newer` to two weeks before
   today, resets `CHANGELOG.md` to an empty skeleton, and runs `uv lock` (a
   lock file still naming the template would fail the first CI run — if the
   lock step warns, run `uv lock` yourself before committing).

   `--github-user` is required: it is baked into the project URLs, and
   leaving it out ships a dead security-report link in
   `.github/ISSUE_TEMPLATE/config.yml`. `--author`, `--email`, and
   `--description` are optional; any omitted placeholder is left as-is.

   Finally the script deletes its own scaffolding — this file,
   `scripts/bootstrap.py`, and `tests/test_bootstrap.py`. Pass
   `--keep-bootstrap` to keep them.
3. Update `pyproject.toml` metadata (keywords, URLs) beyond what the
   script covers
4. Update `README.md`, `SECURITY.md`, and `CLAUDE.md`
5. Replace the placeholder implementation and keep `src/<your_package>/__init__.py`,
   `docs/reference.md`, and the usage examples in sync with your public API
6. **Register PyPI Trusted Publishing** for the new repository before the
   first release. `.github/workflows/release.yml` publishes with
   `uv publish --trusted-publishing always` from the `release` environment
   and fails without it. On PyPI, add a pending publisher with:

   | Field | Value |
   |---|---|
   | Owner | your GitHub user or org |
   | Repository name | the new repository |
   | Workflow name | `release.yml` |
   | Environment name | `release` |

7. **Enable GitHub Pages** for the new repository, serving from the
   `gh-pages` branch (Settings -> Pages -> Source: *Deploy from a branch*).
   `.github/workflows/docs.yml` only pushes that branch; the Documentation
   URL in `README.md` returns 404 until Pages is turned on.

To find any placeholders the script left untouched (e.g. because an
optional argument was omitted):

```bash
rg -n "your-username|my-package|my_package|uv-template|Your Name|you@example" .
```

### Working in the new repository

- **Never commit directly on `main`.** The pre-commit `no-commit-to-branch`
  hook blocks it, and `.claude/hooks/guard.py` blocks `--no-verify`, so the
  way through is a feature branch and a PR — not a bypass flag.
- Python dependencies are updated manually; see
  `.claude/rules/pyproject.md` for the `exclude-newer` procedure.

## Design Philosophy

Every choice in this template has a reason. If you disagree with a decision,
you know exactly what to change and why it was there in the first place.

### Why `src/` layout?

The `src/` layout prevents accidental imports of the local package during
development and testing. It ensures that tests always run against the
*installed* version, catching packaging errors before they reach users.

### Why strict mypy + comprehensive Ruff rules?

Type errors and lint issues are cheapest to fix at write time. Strict settings
from day one mean every line of code is held to the same standard — there is
never a "legacy" codebase to clean up. LLMs generating code also benefit from
strict rules: they produce higher-quality output when constraints are clear.

### Why zero runtime dependencies?

A library template should not impose opinions about logging, HTTP clients, or
data validation. You add what you need. Starting from zero keeps the dependency
tree small and avoids conflicts with downstream users.

### Why Just over Make?

Just has cleaner syntax (no mandatory tabs), better cross-platform support, and
more readable recipe definitions. It is a task runner, not a build system —
which is exactly what a Python project needs.

### Why AGENTS.md and .claude/?

AI-assisted development is the norm, not the exception. `AGENTS.md` gives any
coding agent (Claude Code, Codex, Cursor, Gemini CLI, ...) the context it
needs to match your project's standards; `CLAUDE.md` imports it and adds
Claude Code specifics. The committed `.claude/` directory goes further than
prose: path-scoped rules load conventions only when relevant files are
touched, hooks deterministically auto-format edited files, block edits to
`uv.lock`/`.env*`/`secrets/**` as well as `--no-verify`, force-push, and
`gh pr merge --admin` commands, and run ruff + mypy before the agent ends
a turn, while a reviewed permission allowlist covers local development
commands — commit, push, and PR creation always stay behind human approval.

### Why 80% coverage minimum?

80% is high enough to catch most regressions but low enough to avoid
test-for-the-sake-of-testing. Branch coverage is enabled, so conditional logic
is meaningfully tested.
