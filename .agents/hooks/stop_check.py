# /// script
# requires-python = ">=3.12"
# ///
"""Stop hook: lightweight quality gate before a turn ends.

Runs the same ruff lint + format checks and mypy as `just lint` (no tests —
those stay in `just check` and CI) whenever the working tree contains
modified Python files or pyproject.toml. Exit code 2 blocks the stop and feeds
the failures back to the model so it fixes them before declaring the turn done.

The hook's wall-clock budget is the timeout in the project hook configuration;
a timed-out hook is skipped, not blocking. If this template grows into a
project whose cold-cache whole-tree mypy run exceeds that budget, raise the
configured timeout.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from hook_payload import load_event, project_root

if TYPE_CHECKING:
    from pathlib import Path

# Paths mypy checks when they exist. A repo spawned from this template may
# drop any of them (e.g. scripts/); passing a missing path makes mypy exit
# nonzero with "Cannot read file", which would block every turn end.
MYPY_PATHS = ("src", "scripts", "tests")


def _checks(root: Path) -> list[list[str]]:
    """Build the check commands, skipping mypy when it has nothing to read."""
    checks = [
        ["uv", "run", "ruff", "check", "."],
        ["uv", "run", "ruff", "format", "--check", "."],
    ]
    paths = [path for path in MYPY_PATHS if (root / path).exists()]
    if paths:
        checks.append(["uv", "run", "mypy", *paths])
    return checks


# Drop the wrapper script's own venv so the nested `uv run` targets .venv.
SUBPROCESS_ENV = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}


def _python_files_changed(root: Path) -> bool:
    """Return True when uncommitted changes touch Python code or its config."""
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(root), "status", "--porcelain", "-uall"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        if path.endswith(".py") or path == "pyproject.toml":
            return True
    return False


def main() -> int:
    """Run the lint/type gate unless this stop is a hook-driven continuation."""
    event = load_event()
    if event.name != "Stop":
        return 0

    # A previous block already continued the turn once — never loop.
    if event.stop_hook_active:
        return 0

    root = project_root().resolve()
    if not _python_files_changed(root):
        return 0

    for args in _checks(root):
        result = subprocess.run(  # noqa: S603
            args,
            capture_output=True,
            text=True,
            check=False,
            cwd=root,
            env=SUBPROCESS_ENV,
        )
        if result.returncode != 0:
            sys.stderr.write(f"Quality gate failed ({' '.join(args)}):\n")
            sys.stderr.write(result.stdout)
            sys.stderr.write(result.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
