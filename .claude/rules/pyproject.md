---
paths:
  - "pyproject.toml"
---

- Runtime dependencies go under `[project] dependencies`
- Dev dependencies go under `[dependency-groups] dev`; docs under `[dependency-groups] docs`
- Before adding a dependency: verify active maintenance, compatible license (MIT/BSD/Apache), and minimal transitive dependencies
- Use version ranges (`>=X.Y`) for runtime dependencies -- never pin exact versions in a library
- NEVER remove existing ruff rules without explicit user approval
- NEVER lower the coverage threshold (currently 80%)
- After modifying dependencies, run `uv sync --all-groups`
- The `uv.lock` file MUST be committed alongside dependency changes

## `[tool.uv] exclude-newer`

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

1. Set the `exclude-newer` date in `pyproject.toml` to roughly "today minus
   14 days".
2. Run `uv lock --upgrade` to move dependencies up to the new cutoff.
3. Run `just check`.
4. Commit `pyproject.toml` and `uv.lock` together in the same commit.
