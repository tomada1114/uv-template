---
paths:
  - "pyproject.toml"
---

- Runtime dependencies go under `[project] dependencies`
- Dev dependencies go under `[dependency-groups] dev`
- Docs dependencies go under `[dependency-groups] docs`
- NEVER remove existing ruff rules without explicit user approval
- NEVER lower the coverage threshold (currently 80%)
- After modifying dependencies, run `uv sync --all-groups`
- The `uv.lock` file MUST be committed alongside dependency changes
