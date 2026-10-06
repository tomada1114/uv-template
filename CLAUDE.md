@AGENTS.md

# Claude Code Specifics

Shared, tool-agnostic project instructions live in `AGENTS.md` (imported
above). This file only records what Claude Code adds on top of them.

- `.claude/settings.json` holds only the wiring for the shared hooks in
  `.agents/hooks/`. No permission rule or plugin marketplace is committed;
  personal settings belong in `~/.claude/settings.json` or the gitignored
  `.claude/settings.local.json`.
- `.claude/skills/` is a generated mirror of `.agents/skills/`. Never hand-edit
  it: edit `.agents/skills/`, run `just agents-sync`, and commit both.
- Hand a step to a sub-agent tier by `subagent_type` — `executor`, `architect`,
  or `worker` — never by a bare `model`, which runs at the session's default
  effort rather than the tier's. The definitions in `.claude/agents/` shadow
  same-named ones in `~/.claude/agents/` inside this repository.
