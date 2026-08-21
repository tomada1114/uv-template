<!-- agents-md-sync:begin -->
@AGENTS.md
<!-- agents-md-sync:end -->

# Claude Code Specifics

Shared, tool-agnostic project instructions live in `AGENTS.md` (imported
above). This repo additionally ships Claude Code configuration:

- `.claude/settings.json` — the host-specific permission allowlist and wiring
  for the shared hooks. It allows the local `just` recipes, `uv` commands,
  and read-only `git`/`gh` inspection in the `:*` form; commit, push, and PR
  creation still require approval. Personal settings belong in
  `.claude/settings.local.json`, never here
- `.claude/skills/` — the canonical source for `create-pr`, `smart-commit`,
  `merge-dependabot`, and `release-workflow`
- `.agents/skills/` — generated symlinks for the same skills; edit the
  corresponding `.claude/skills/` directory instead of the symlink
- `.agents/hooks/` — shared hook implementations described in `AGENTS.md`
