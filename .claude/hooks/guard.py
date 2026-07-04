# /// script
# requires-python = ">=3.12"
# ///
"""PreToolUse hook: block edits to protected files and dangerous git commands.

Permission `deny` rules are advisory in some Claude Code versions
(anthropics/claude-code#6699), and hooks also fire in bypassPermissions mode,
so this hook is the enforcement backstop for the rules below.

Exit code 2 blocks the tool call and shows the reason to Claude.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import PurePosixPath

# uv.lock must only change via `uv lock` / `uv add`; .env files hold secrets.
PROTECTED_WRITE_MESSAGES = {
    "uv.lock": "uv.lock is generated — run `uv lock` or `uv add` instead of editing it.",
    ".env": "Files named .env* may contain secrets and must not be written by the agent.",
}
ENV_EXAMPLE_SUFFIXES = (".example", ".sample", ".template")


def _check_write(file_path: str) -> str | None:
    """Return a block reason when the target file must not be hand-edited."""
    name = PurePosixPath(file_path.replace("\\", "/")).name
    if name == "uv.lock":
        return PROTECTED_WRITE_MESSAGES["uv.lock"]
    if name.startswith(".env") and not name.endswith(ENV_EXAMPLE_SUFFIXES):
        return PROTECTED_WRITE_MESSAGES[".env"]
    return None


def _check_bash(command: str) -> str | None:
    """Return a block reason when the shell command bypasses quality gates."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    if "git" not in tokens:
        return None

    if re.search(r"\bgit\b.*\bcommit\b", command) and (
        "--no-verify" in tokens or "-n" in tokens
    ):
        return "git commit --no-verify skips the pre-commit hooks — fix the failing hook instead."

    if re.search(r"\bgit\b.*\bpush\b", command):
        force_flags = {"--force", "-f"} & set(tokens)
        if force_flags and "--force-with-lease" not in tokens:
            return "Plain force-push is blocked — use `git push --force-with-lease` if a force-push is really needed."

    return None


def main() -> int:
    """Inspect the pending tool call and block protected operations."""
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    reason = None
    if tool_name in {"Edit", "Write"}:
        reason = _check_write(tool_input.get("file_path", ""))
    elif tool_name == "Bash":
        reason = _check_bash(tool_input.get("command", ""))

    if reason:
        sys.stderr.write(f"Blocked: {reason}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
