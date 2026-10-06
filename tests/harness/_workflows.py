"""Reads GitHub Actions workflows through the fail-closed `_yaml` scanner.

Shared by the ruleset check (which jobs run on every pull request) and the
workflow hygiene check (triggers, jobs, steps). Any layout the scanner cannot
read raises `UnreadableYamlError`, so a workflow is never classified as running
on every pull request, or as clean, by accident.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.harness._yaml import (
    Entry,
    Mapping,
    UnreadableYamlError,
    content_lines,
    flow_list,
    mapping,
    scalar,
    sequence,
)

if TYPE_CHECKING:
    from pathlib import Path

WORKFLOWS_DIR = ".github/workflows"

_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.(?P<key>[A-Za-z0-9_-]+)\s*\}\}")
_EXPR = re.compile(r"^\$\{\{\s*(?P<body>.*?)\s*\}\}$")
_GUARDS = {"!cancelled()", "always()"}


@dataclass(frozen=True, slots=True)
class Check:
    """One check run a workflow job produces."""

    name: str
    if_expr: str | None
    has_needs: bool


def workflow_files(root: Path) -> list[Path]:
    """Return every workflow file under ``root``, sorted."""
    return sorted((root / WORKFLOWS_DIR).glob("*.y*ml"))


def read_workflow(path: Path) -> Mapping:
    """Return a workflow's top-level mapping."""
    return mapping(content_lines(path.read_text(encoding="utf-8")), path)


def triggers(top: Mapping, path: Path) -> Mapping:
    """Return ``event -> (inline value, block)`` for each event of ``on:``."""
    on = top.get("on") or top.get("true")
    if on is None:
        msg = f"{path.name}: no `on:` trigger"
        raise UnreadableYamlError(msg)
    value, block = on
    if not value:
        return mapping(block, path)
    events = flow_list(value, path)
    return {event: ("", []) for event in events or [scalar(value)]}


def jobs(top: Mapping, path: Path) -> dict[str, Mapping]:
    """Return each job's mapping by job id."""
    return {
        job_id: mapping(lines, path)
        for job_id, (_, lines) in mapping(top.get("jobs", ("", []))[1], path).items()
    }


def steps(job: Mapping, path: Path) -> list[Mapping]:
    """Return each step's mapping."""
    value, block = job.get("steps", ("", []))
    if value:
        msg = f"{path.name}: cannot read steps: {value!r}"
        raise UnreadableYamlError(msg)
    return [mapping(item, path) for item in sequence(block, path)]


def _unfiltered_pull_request(events: Mapping, path: Path) -> bool:
    if "pull_request" not in events:
        return False
    pr_value, pr_block = events["pull_request"]
    if pr_value not in {"", "{}"}:
        msg = f"{path.name}: cannot read pull_request: {pr_value!r}"
        raise UnreadableYamlError(msg)
    return not {"paths", "paths-ignore"} & mapping(pr_block, path).keys()


def _matrix_values(job: Mapping, key: str, path: Path) -> list[str]:
    strategy = mapping(job.get("strategy", ("", []))[1], path)
    matrix = mapping(strategy.get("matrix", ("", []))[1], path)
    if key not in matrix:
        msg = f"{path.name}: matrix.{key} is not declared in the job's matrix"
        raise UnreadableYamlError(msg)
    values = flow_list(matrix[key][0], path)
    if values is None:
        msg = f"{path.name}: matrix.{key} must be a one-line [a, b] list"
        raise UnreadableYamlError(msg)
    return values


def _checks(path: Path) -> list[Check] | None:
    """Return the checks of a workflow that runs on every PR, else ``None``."""
    top = read_workflow(path)
    if not _unfiltered_pull_request(triggers(top, path), path):
        return None
    checks: list[Check] = []
    for job_id, job in jobs(top, path).items():
        names = [scalar(job.get("name", (job_id, []))[0]) or job_id]
        for key in _MATRIX_REF.findall(names[0]):
            pattern = re.compile(rf"\$\{{\{{\s*matrix\.{key}\s*\}}\}}")
            names = [
                pattern.sub(value, name)
                for name in names
                for value in _matrix_values(job, key, path)
            ]
        if_expr = job["if"][0] if "if" in job else None
        checks.extend(Check(name, if_expr, "needs" in job) for name in names)
    return checks


def every_pr_checks(workflows_dir: Path) -> dict[str, Check]:
    """Return checks from workflows whose pull_request trigger is unfiltered."""
    found: dict[str, Check] = {}
    for path in sorted(workflows_dir.glob("*.y*ml")):
        for check in _checks(path) or []:
            found[check.name] = check
    return found


def can_skip(check: Check) -> bool:
    """Whether a job's ``if:`` (or a failed ``needs:``) could skip its check."""
    if check.if_expr is None:
        return check.has_needs
    match = _EXPR.match(check.if_expr.strip("\"'"))
    body = match["body"] if match else check.if_expr
    return body not in _GUARDS


def entry_value(entry: Entry | None) -> str | None:
    """Return an entry's inline scalar, or None when the key is absent."""
    return None if entry is None else scalar(entry[0])
