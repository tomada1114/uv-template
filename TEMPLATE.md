# About This Template

This file documents how to turn a copy of the template into a real application.
`scripts/bootstrap.py` deletes it from the spawned repo, so nothing here ships with
your application. Why the template is built the way it is lives with each subject in
the skill that owns it (`AGENTS.md`'s Skills table), so the reasons ship with every
app and stay next to the rules they explain.

## Using This Template

The steps live in one place: the `starting-an-app` skill
(`.agents/skills/starting-an-app/SKILL.md`, mirrored to `.claude/skills/`). It gives
the order of work from "Use this template" to the first feature — the bootstrap, the
Product section, labels, the GitHub settings, the ruleset, removing the sample — and
marks which steps are a human's. Its `references/bootstrap.md` documents
`scripts/bootstrap.py`: the flags, what it refuses, and what it rewrites and removes.

### Working in the new repository

- **Never commit directly on `main`.** The pre-commit `no-commit-to-branch`
  hook blocks it, and `--no-verify` would also switch off the secret gate
  (`scripts/check_staged.py`), so the way through is a feature branch and a
  PR — not a bypass flag.
- The toolchain baseline checklist lives in `changing-gates` so every app keeps it.
- Python dependencies arrive as monthly Dependabot `uv` PRs under a 7-day
  cooldown equal to `[tool.uv] exclude-newer = "7 days"`; a human merges
  them with the `merging-dependency-prs` skill, and `managing-dependencies`
  holds the window and its one-package exception.
- `just verify` (its steps are listed in AGENTS.md's Quick Reference) is the
  non-mutating gate for a PR or a completion claim; `just check` mutates the
  tree first (`fmt`) and is for local iteration only.
