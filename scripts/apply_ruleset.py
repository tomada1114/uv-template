"""Create or update the default-branch ruleset from `.github/rulesets/main.json`.

The JSON file is the single source of truth for the ruleset. It is upserted by
name through `gh api repos/{owner}/{repo}/rulesets`: created when no ruleset
carries its name, updated in place by id when one does. The script never
deletes a ruleset, so one a person added by hand survives. Writing rulesets
needs repository admin rights, so running it is a human step.

Usage:
    uv run --locked python scripts/apply_ruleset.py                 # apply via gh
    uv run --locked python scripts/apply_ruleset.py --repo OWNER/REPO
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RULESET_FILE = REPO_ROOT / ".github" / "rulesets" / "main.json"
REQUIRED_KEYS = ("name", "target", "enforcement", "conditions", "rules")
HUMAN_STEP = (
    "a repository admin runs `just ruleset` with an authenticated `gh` "
    "(`gh auth status`)"
)
_DENIED_MARKERS = ("HTTP 403", "HTTP 404")


class RulesetFileError(ValueError):
    """The ruleset file is unreadable, not JSON, or lacks a required key."""


class GhError(RuntimeError):
    """A `gh` invocation exited non-zero."""


def load_ruleset(path: Path) -> dict[str, Any]:
    """Read and validate the ruleset JSON.

    Returns:
        The parsed ruleset. ``Any``: values are arbitrary JSON.

    Raises:
        RulesetFileError: On an unreadable file, invalid JSON, a non-object
            document, or a missing required key.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RulesetFileError(str(error)) from error
    except json.JSONDecodeError as error:
        msg = f"invalid JSON: {error}"
        raise RulesetFileError(msg) from error
    if not isinstance(data, dict):
        msg = "top level must be a JSON object"
        raise RulesetFileError(msg)
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        msg = f"missing required keys: {missing}"
        raise RulesetFileError(msg)
    if not isinstance(data["name"], str) or not data["name"]:
        msg = "name must be a non-empty string"
        raise RulesetFileError(msg)
    return data


def _gh(args: list[str], stdin: str | None = None) -> str:
    command = ["gh", *args]
    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        command, check=False, capture_output=True, text=True, input=stdin
    )
    if result.returncode != 0:
        msg = f"gh {' '.join(args)}: {result.stderr.strip()}"
        raise GhError(msg)
    return result.stdout


def current_repo() -> str:
    """Return ``owner/repo`` of the checkout, as `gh repo view` reports it."""
    return _gh(
        ["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"]
    ).strip()


def find_ruleset_id(repo: str, name: str) -> int | None:
    """Return the id of the repository ruleset called ``name``, if any."""
    listed = json.loads(_gh(["api", f"repos/{repo}/rulesets", "--paginate"]) or "[]")
    for entry in listed:
        if entry.get("name") == name:
            return int(entry["id"])
    return None


def upsert_command(repo: str, ruleset_id: int | None) -> list[str]:
    """Return the `gh api` argv that creates (POST) or updates (PUT) the ruleset."""
    if ruleset_id is None:
        return ["api", "--method", "POST", f"repos/{repo}/rulesets", "--input", "-"]
    return [
        "api",
        "--method",
        "PUT",
        f"repos/{repo}/rulesets/{ruleset_id}",
        "--input",
        "-",
    ]


def _fail(code: str, detail: str, expected: str, next_step: str) -> int:
    print(f"{code}: {detail}", file=sys.stderr)
    print(f"Expected: {expected}", file=sys.stderr)
    print(f"Next: {next_step}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None, ruleset_file: Path = RULESET_FILE) -> int:
    """Upsert the ruleset and return an exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", help="OWNER/REPO; defaults to `gh repo view`")
    args = parser.parse_args(argv)
    try:
        ruleset = load_ruleset(ruleset_file)
    except RulesetFileError as error:
        return _fail(
            "ERR_RULESET_FILE",
            f"{ruleset_file}: {error}",
            f"a JSON object with keys {list(REQUIRED_KEYS)}",
            f"fix {ruleset_file} and rerun `just ruleset`",
        )
    try:
        repo = args.repo or current_repo()
        ruleset_id = find_ruleset_id(repo, ruleset["name"])
        output = _gh(upsert_command(repo, ruleset_id), stdin=json.dumps(ruleset))
    except GhError as error:
        detail = str(error)
        denied = any(marker in detail for marker in _DENIED_MARKERS)
        return _fail(
            "ERR_RULESET_GH",
            detail,
            "an authenticated `gh` with admin rights on the repository",
            HUMAN_STEP if denied else "check `gh auth status` and rerun `just ruleset`",
        )
    applied = json.loads(output)
    verb = "created" if ruleset_id is None else "updated"
    print(f"{verb}: ruleset {ruleset['name']!r} id {applied.get('id', ruleset_id)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
