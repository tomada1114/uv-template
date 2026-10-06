<!-- platform-annex -->
# Platform notes

## Tool mapping

- The bundled survey is invoked through the repository's generated `.agents/skills` bridge.
- GitHub CLI, Git, uv, and the project task runner require the normal host approval for network or repository writes.
- The single approval gate in the operating contract remains a plain user conversation when a selection prompt is unavailable.

## Codex constraints

This is a best-effort fallback for a runtime whose capabilities are not publicly
available to the skill; it is not a product feature matrix.

- If a Git, uv, or test command fails with `Operation not permitted`, rerun that exact command through the host's approved elevated execution path. If a tool cache is unwritable, point its cache environment variable at a writable temporary directory; never delete lock files or bypass the failed operation.
- The survey and merge sequence remains ordered; any unavailable delegation only increases runtime and keeps all triage output in the main context.
