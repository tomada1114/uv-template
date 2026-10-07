"""Reads GitHub Actions workflows through the fail-closed `_yaml` scanner.

Shared by the ruleset check (which jobs run on every pull request, and whether
a job with ``needs:`` fails on its own) and the workflow hygiene check
(triggers, jobs, steps). Any layout the scanner cannot read raises
`UnreadableYamlError`, so a workflow is never classified as running on every
pull request, or as clean, by accident.

A step "fails on a non-success ``needs.<job>.result``" when it has a ``run:``
that exits with a literal non-zero status (``exit 1``) and no
``continue-on-error``, and either

- its ``if:`` is absent, ``always()``, or ``!cancelled()``, and a ``run:`` line
  that mentions ``success`` reads the result, inline as
  ``${{ needs.<job>.result }}`` or through a step or job ``env:`` variable set
  from it; or
- its ``if:`` is ``needs.<job>.result != 'success'``, alone or joined by ``||``.

The shell is read as text, not run: an inverted comparison passes. Any other
spelling (``needs.*.result``, ``contains(...)``, a step ``if:`` with another
condition) is not recognized, so it fails rather than passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

from tests.harness._yaml import (
    Entry,
    Mapping,
    UnreadableYamlError,
    block_text,
    content_lines,
    flow_list,
    mapping,
    scalar,
    scalar_list,
    sequence,
    split_comment,
)

if TYPE_CHECKING:
    from pathlib import Path

WORKFLOWS_DIR = ".github/workflows"

_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.(?P<key>[A-Za-z0-9_-]+)\s*\}\}")
_EXPR = re.compile(r"^\$\{\{\s*(?P<body>.*?)\s*\}\}$")
_GUARDS = {"!cancelled()", "always()"}
_JOB_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_RESULT_REF = re.compile(r"\bneeds\.(?P<job>[A-Za-z_][A-Za-z0-9_-]*)\.result\b")
_NOT_SUCCESS = re.compile(
    r"^\(?\s*needs\.(?P<job>[A-Za-z_][A-Za-z0-9_-]*)\.result\s*!=\s*'success'\s*\)?$"
)
_EXIT_FAILURE = re.compile(r"(?<![\w-])exit\s+[1-9][0-9]*(?![\w-])")
_SUCCESS = re.compile(r"\bsuccess\b")
# The ruleset protects the default branch; a pull_request filter has to let a PR
# into it through, on each of the events a PR's checks are reported for.
DEFAULT_BRANCH = "main"
PR_ACTIVITY = frozenset({"opened", "synchronize", "reopened"})
_PR_FILTERS = frozenset(
    {"types", "branches", "branches-ignore", "paths", "paths-ignore"}
)


@dataclass(frozen=True, slots=True)
class Check:
    """One check run a workflow job produces."""

    name: str
    if_expr: str | None
    has_needs: bool
    # The needed jobs no step fails on when their result is not success.
    unfailed_needs: tuple[str, ...] = ()


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
    filters = mapping(pr_block, path)
    if unknown := sorted(filters.keys() - _PR_FILTERS):
        msg = f"{path.name}: unknown pull_request filter {unknown}"
        raise UnreadableYamlError(msg)
    if {"paths", "paths-ignore", "branches-ignore"} & filters.keys():
        return False
    if "branches" in filters:
        patterns = scalar_list(filters["branches"], path)
        # A `!` pattern re-excludes branches; reading the order is not worth it.
        if any(p.startswith("!") for p in patterns) or not any(
            fnmatchcase(DEFAULT_BRANCH, p) for p in patterns
        ):
            return False
    if "types" in filters:
        return set(scalar_list(filters["types"], path)) >= PR_ACTIVITY
    return True


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


def _needs(job: Mapping, path: Path) -> list[str]:
    """Return the job ids a job's ``needs:`` names."""
    if "needs" not in job:
        return []
    names = scalar_list(job["needs"], path)
    if not names or not all(_JOB_ID.match(name) for name in names):
        msg = f"{path.name}: cannot read `needs: {job['needs'][0]}`"
        raise UnreadableYamlError(msg)
    return names


def _env(entry: Entry | None, path: Path) -> dict[str, str]:
    """Return an ``env:`` block's ``name -> value``."""
    if entry is None:
        return {}
    value, block = entry
    if value:
        msg = f"{path.name}: cannot read an inline `env: {value}`"
        raise UnreadableYamlError(msg)
    return {name: scalar(text) for name, (text, _) in mapping(block, path).items()}


def _expression_body(expr: str) -> str:
    match = _EXPR.match(expr.strip("\"'"))
    return match["body"] if match else expr


def _results_compared(code: str, env: dict[str, str]) -> set[str]:
    """Return the jobs whose result one ``run:`` line compares with success."""
    if not _SUCCESS.search(code):
        return set()
    sources = [code]
    sources.extend(
        value
        for name, value in env.items()
        if re.search(rf"\$\{{?{re.escape(name)}(?![A-Za-z0-9_])", code)
    )
    return {match["job"] for text in sources for match in _RESULT_REF.finditer(text)}


def _failed_needs(step: Mapping, job_env: dict[str, str], path: Path) -> set[str]:
    """Return the needed jobs whose non-success result makes this step fail."""
    if "run" not in step or entry_value(step.get("continue-on-error")) not in {
        None,
        "false",
    }:
        return set()
    lines = [split_comment(line)[0] for line in block_text(step["run"]).splitlines()]
    if not any(_EXIT_FAILURE.search(line) for line in lines):
        return set()
    if_expr = entry_value(step.get("if"))
    if if_expr is not None and (body := _expression_body(if_expr)) not in _GUARDS:
        terms = [_NOT_SUCCESS.match(term.strip()) for term in body.split("||")]
        return {term["job"] for term in terms if term} if all(terms) else set()
    env = {**job_env, **_env(step.get("env"), path)}
    return {job for line in lines for job in _results_compared(line, env)}


def _unfailed_needs(job: Mapping, path: Path) -> tuple[str, ...]:
    """Return the needed jobs no step of ``job`` fails on."""
    needed = _needs(job, path)
    if not needed:
        return ()
    job_env = _env(job.get("env"), path)
    failed = {
        name for step in steps(job, path) for name in _failed_needs(step, job_env, path)
    }
    return tuple(name for name in needed if name not in failed)


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
        if_expr = split_comment(job["if"][0])[0] if "if" in job else None
        unfailed = _unfailed_needs(job, path)
        checks.extend(Check(name, if_expr, "needs" in job, unfailed) for name in names)
    return checks


def every_pr_checks(workflows_dir: Path) -> dict[str, Check]:
    """Return checks from workflows whose pull_request trigger is unfiltered.

    Two jobs with one name report one context; they merge into one check that
    keeps the skippable one's ``if:`` and every unfailed need of both, so a
    duplicate can only make the judgement stricter.
    """
    found: dict[str, Check] = {}
    for path in sorted(workflows_dir.glob("*.y*ml")):
        for check in _checks(path) or []:
            found[check.name] = (
                _stricter(found[check.name], check) if check.name in found else check
            )
    return found


def _stricter(kept: Check, other: Check) -> Check:
    base = other if can_skip(other) and not can_skip(kept) else kept
    unfailed = dict.fromkeys((*kept.unfailed_needs, *other.unfailed_needs))
    return replace(base, unfailed_needs=tuple(unfailed))


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
