# The pre-commit layer

Read before editing `.pre-commit-config.yaml` or `scripts/check_staged.py`, or when a
commit, a merge, or `just install` behaves unexpectedly around the hooks. The hook list
itself is `.pre-commit-config.yaml`'s; read it there.

The guard rails run as git hooks through [pre-commit](https://pre-commit.com/), so they
hold for every author — a human, Claude Code, Codex CLI, or any other tool. No
agent-specific hook is committed.

## `check-staged`, the secret gate

`check-staged` (`scripts/check_staged.py`) refuses a commit that stages a secret-shaped
path or secret-shaped content. Its module docstring and constants are the list; in
summary:

- **Paths:** `.env` and `.env.*` except `.env.example`; `.envrc` and `.envrc.*`;
  anything under `secrets/`; `*.pem`, `*.key`, `id_rsa*`;
  `.claude/settings.local.json` at any depth; `.codex/rules/local.rules`.
- **Content:** an AWS access key; a GitHub, Anthropic, OpenAI project, OpenRouter,
  Slack, or Stripe live token; a PEM private-key header.
- It judges the index, not the working tree, so a partially staged file is judged as it
  will be committed. It names the file and the kind of secret and never prints the
  matched value.
- It is stdlib-only and runs with pre-commit's own interpreter (`language: python`), so
  it needs no uv; ruff holds it to Python 3.10 syntax for that reason.
- A staged deletion is never inspected: removing a file cannot add a secret.

## When the hooks run, and when they do not

- `check-staged` runs on every `git commit`, including the one that concludes a
  conflicted merge, and on clean merges through git's `pre-merge-commit` hook. In a
  merge, content identical to what the merged-in branch already has at the same path is
  not judged again; conflict resolutions and other new content are. It is the only hook
  at `pre-merge-commit`; every other hook runs on `git commit` only.
- Commits that git makes itself run no pre-commit hook at all: the commits `git rebase`
  replays (including after `git rebase --continue`), `git cherry-pick`, and
  `git revert`. The backstop for those is the weekly full-history gitleaks scan in
  `.github/workflows/security-audit.yml`.

## Installing the hooks

- `just install` installs both git hooks and fails when either is missing afterwards.
  With `ALLOW_MISSING_GIT_HOOKS=1` or `CI=true` it still attempts the install, but a
  failed install or a missing hook is only a warning. Outside a Git repository it skips
  the hooks.
- A checkout installed before the `pre-merge-commit` hook existed has only the
  `pre-commit` hook: re-run `just install` to add it.
- Git hooks live in the main checkout's `.git/hooks/` and are shared by every linked
  worktree. Run `just install` from the main checkout: run from a worktree, it points
  the shared hooks at that worktree's `.venv`.

## What replaced the agent hooks

The repository used to wire agent hook scripts into Claude Code and Codex CLI. Each
behavior they had now lives here:

| Former agent hook behavior | Where it lives now |
|---|---|
| Format-on-edit (`format.py`) | An opt-in personal hook in the gitignored `.claude/settings.local.json` (snippet below) |
| Blocking `git commit --no-verify`, plain force-push, `gh pr merge --admin` (`guard.py`) | The owner's user-level deny rules, plus "never bypass a git hook" in AGENTS.md's "Security and human approval" |
| Blocking writes to `uv.lock` (`guard.py`) | `just verify`'s `lock-check` (`uv lock --check`) |
| Blocking writes to `.env*` and `secrets/**` (`guard.py`) | `check-staged` refuses them at commit time |
| ruff and mypy before an agent ends its turn (`stop_check.py`) | The ruff and mypy pre-commit hooks, and `just verify` |

Format-on-edit for Claude Code, in `.claude/settings.local.json` (needs `jq`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "f=$(jq -r '.tool_input.file_path // empty'); case \"$f\" in *.py) cd \"$CLAUDE_PROJECT_DIR\" && uv run --locked ruff check --fix --quiet \"$f\"; uv run --locked ruff format --quiet \"$f\" ;; esac; exit 0"
          }
        ]
      }
    ]
  }
}
```
