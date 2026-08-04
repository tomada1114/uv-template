@AGENTS.md

# Claude Code Specifics

Shared, tool-agnostic project instructions live in `AGENTS.md` (imported
above). This repo additionally ships Claude Code configuration:

- `.claude/rules/` — path-scoped conventions (Python, tests, docs,
  pyproject.toml) that load automatically when matching files are read
- `.claude/hooks/format.py` — runs `ruff check --fix` and `ruff format` on
  every edited `*.py` file (PostToolUse), so do not re-run formatters or
  lint autofixes after each edit
- `.claude/hooks/guard.py` — blocks writes to `uv.lock`, `.env*`, and
  `secrets/**` (via Edit/Write or shell commands), `git commit --no-verify`,
  plain force-pushes, and `gh pr merge --admin` (PreToolUse)
- `.claude/hooks/stop_check.py` — runs ruff (lint + format check) and mypy
  before a turn ends when `*.py` files or `pyproject.toml` changed (Stop)
- `.claude/skills/` — `create-pr`, `smart-commit`, `merge-dependabot`, and
  `release-workflow` workflow skills
- `.claude/settings.json` — shared permission allowlist for the local
  `just` recipes, `uv` commands, and read-only `git`/`gh` inspection,
  every entry in the `:*` form; commit, push, and PR creation still
  require approval. Personal preferences (model, output style, extra
  permissions) belong in `.claude/settings.local.json`, never here
