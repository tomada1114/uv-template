<!-- platform-annex -->
# Platform notes

## Tool mapping

- Dynamic context commands in this skill are run explicitly at the start of the workflow.
- The `create-pr` skill is a shared skill reference and is available through the repository skill bridge.
- Git operations require the normal host approval for repository writes and pushes.

## Codex constraints

This is a best-effort fallback for a runtime whose capabilities are not publicly
available to the skill; it is not a product feature matrix.

- If a Git command fails with `Operation not permitted`, rerun that exact command through the host's approved elevated execution path. If a tool cache is unwritable, point its cache environment variable at a writable temporary directory; never delete lock files or bypass the failed operation.
- Dynamic context injection is replaced by explicit command execution, so the workflow spends a few extra steps collecting state but preserves the same commit decisions.
