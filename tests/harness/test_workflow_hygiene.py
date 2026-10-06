"""(f) Every workflow is pinned, least-privileged, bounded, and fails closed.

Per workflow under ``.github/workflows/``:

- every non-local ``uses:`` (a step's, or a job's reusable-workflow call) is
  ``owner/repo[/path]@<40-hex SHA>`` with a ``# v<version>`` comment, the form
  Dependabot keeps when it bumps a pin; a local ``./`` action is skipped;
- every job sets ``timeout-minutes`` (a reusable-workflow call cannot, and is
  exempt);
- the top-level ``permissions`` is ``{}`` or exactly ``contents: read``; a job
  that needs more declares it on the job;
- every ``actions/checkout`` step sets ``persist-credentials: false``;
- no ``pull_request_target`` trigger, no ``continue-on-error`` other than
  ``false`` on a job or step, and no ``|| true`` on a non-comment line;
- on a workflow triggered on ``push``, no concurrency (top-level or a job's)
  cancels a push run on main: ``cancel-in-progress`` is absent, ``false``, or
  ``${{ github.event_name == 'pull_request' }}``, and the group names
  ``github.sha``, ``github.run_id``, or ``github.run_number``, because GitHub
  also cancels a *pending* run when a newer one joins its group. The group is
  read as text, not evaluated.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.harness._workflows import (
    WORKFLOWS_DIR,
    entry_value,
    jobs,
    read_workflow,
    steps,
    triggers,
    workflow_files,
)
from tests.harness._yaml import (
    Entry,
    Mapping,
    UnreadableYamlError,
    mapping,
    scalar,
    split_comment,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    type MakeWorkflow = Callable[[str], Path]

REPO_ROOT = Path(__file__).resolve().parents[2]
MINIMAL_PERMISSIONS: tuple[dict[str, str], ...] = ({}, {"contents": "read"})
SAFE_CANCEL = frozenset({"false", "${{ github.event_name == 'pull_request' }}"})
PER_RUN_CONTEXTS = ("github.sha", "github.run_id", "github.run_number")
CHECKOUT = "actions/checkout"

_PINNED = re.compile(r"^[\w.-]+/[\w.-]+(?:/[^@\s]+)?@[0-9a-f]{40}$")
_VERSION_COMMENT = re.compile(r"^#\s*v\d")
_OR_TRUE = re.compile(r"\|\|\s*true\b")


def _pin_problems(entry: Entry, where: str) -> list[str]:
    text, comment = split_comment(entry[0])
    ref = scalar(text)
    if ref.startswith("./"):
        return []
    if not _PINNED.match(ref):
        return [f"{where}: `uses: {ref}` is not pinned to a full commit SHA"]
    if comment is None or not _VERSION_COMMENT.match(comment):
        return [f"{where}: `uses: {ref}` has no `# v<version>` comment"]
    return []


def _permissions(entry: Entry | None, path: Path) -> dict[str, str] | None:
    """Return the top-level permissions as a dict, or None for a shorthand."""
    if entry is None:
        return None
    value, block = entry
    if value:
        return {} if scalar(value) == "{}" and not block else None
    return {key: scalar(scope) for key, (scope, _) in mapping(block, path).items()}


def _concurrency_problems(entry: Entry, where: str, path: Path) -> list[str]:
    value, block = entry
    if value:
        group, cancel = scalar(value), None
    else:
        settings = mapping(block, path)
        group = entry_value(settings.get("group")) or ""
        cancel = entry_value(settings.get("cancel-in-progress"))
    problems: list[str] = []
    if cancel is not None and " ".join(cancel.split()) not in SAFE_CANCEL:
        problems.append(
            f"{where}: `cancel-in-progress: {cancel}` can cancel a push run on main"
        )
    if not any(context in group for context in PER_RUN_CONTEXTS):
        problems.append(
            f"{where}: concurrency group {group!r} is shared by push runs, so a "
            "newer push cancels a pending one"
        )
    return problems


def _continue_on_error(entry: Entry | None, where: str) -> list[str]:
    value = entry_value(entry)
    if value is None or value == "false":
        return []
    return [f"{where}: `continue-on-error: {value}` lets a failure pass"]


def _keeps_credentials(step: Mapping, path: Path) -> bool:
    value, block = step.get("with", ("", []))
    if value:
        msg = f"{path.name}: cannot read a checkout step's `with: {value}`"
        raise UnreadableYamlError(msg)
    persist = entry_value(mapping(block, path).get("persist-credentials"))
    return persist != "false"


def _step_problems(step: Mapping, where: str, path: Path) -> list[str]:
    problems = _continue_on_error(step.get("continue-on-error"), where)
    if "uses" not in step:
        return problems
    problems.extend(_pin_problems(step["uses"], where))
    is_checkout = scalar(step["uses"][0]).split("@")[0] == CHECKOUT
    if is_checkout and _keeps_credentials(step, path):
        problems.append(f"{where}: actions/checkout without persist-credentials: false")
    return problems


def _job_problems(job_id: str, job: Mapping, path: Path, *, is_push: bool) -> list[str]:
    relative = f"{WORKFLOWS_DIR}/{path.name}"
    where = f"{relative}: job {job_id!r}"
    problems = _continue_on_error(job.get("continue-on-error"), where)
    if "uses" in job:
        problems.extend(_pin_problems(job["uses"], where))
    elif "timeout-minutes" not in job:
        problems.append(f"{where}: no timeout-minutes")
    if is_push and "concurrency" in job:
        problems.extend(_concurrency_problems(job["concurrency"], where, path))
    for number, step in enumerate(steps(job, path), start=1):
        name = entry_value(step.get("name"))
        label = f"{where} step {number}" + (f" ({name})" if name else "")
        problems.extend(_step_problems(step, label, path))
    return problems


def workflow_problems(path: Path) -> list[str]:
    """Return every hygiene problem of one workflow file."""
    relative = f"{WORKFLOWS_DIR}/{path.name}"
    top = read_workflow(path)
    events = triggers(top, path)
    problems: list[str] = []
    if "pull_request_target" in events:
        problems.append(f"{relative}: triggers on pull_request_target")
    if _permissions(top.get("permissions"), path) not in MINIMAL_PERMISSIONS:
        problems.append(
            f"{relative}: top-level permissions must be {{}} or contents: read"
        )
    lines = path.read_text(encoding="utf-8").splitlines()
    problems.extend(
        f"{relative}:{number}: `|| true` swallows a failure"
        for number, line in enumerate(lines, start=1)
        if not line.lstrip().startswith("#") and _OR_TRUE.search(line)
    )
    is_push = "push" in events
    if is_push and "concurrency" in top:
        problems.extend(_concurrency_problems(top["concurrency"], relative, path))
    for job_id, job in jobs(top, path).items():
        problems.extend(_job_problems(job_id, job, path, is_push=is_push))
    return problems


def hygiene_findings(root: Path) -> list[str]:
    """Return every hygiene problem across the workflows under ``root``."""
    return [
        problem for path in workflow_files(root) for problem in workflow_problems(path)
    ]


# --- the repository ---


def test_workflows_on_repository_are_hygienic() -> None:
    assert workflow_files(REPO_ROOT)
    assert hygiene_findings(REPO_ROOT) == []


# --- fixtures ---

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
CLEAN = f"""\
name: W

on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.event_name == 'pull_request' && github.ref || github.sha }}}}
  cancel-in-progress: ${{{{ github.event_name == 'pull_request' }}}}

jobs:
  build:
    name: Build
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@{SHA} # v7.0.1
        with:
          persist-credentials: false
      - uses: ./.github/actions/local
      - name: Test
        run: |
          set -euo pipefail
          # never `|| true` here
          uv run pytest
"""


@pytest.fixture
def make_workflow(tmp_path: Path) -> MakeWorkflow:
    def make(text: str) -> Path:
        (tmp_path / WORKFLOWS_DIR).mkdir(parents=True, exist_ok=True)
        (tmp_path / WORKFLOWS_DIR / "w.yml").write_text(text, encoding="utf-8")
        return tmp_path

    return make


def test_hygiene_findings_clean_workflow_passes(make_workflow: MakeWorkflow) -> None:
    assert hygiene_findings(make_workflow(CLEAN)) == []


def test_hygiene_findings_without_workflows_passes(tmp_path: Path) -> None:
    assert hygiene_findings(tmp_path) == []


W = f"{WORKFLOWS_DIR}/w.yml"
JOB = f"{W}: job 'build'"


@pytest.mark.parametrize(
    ("old", "new", "finding"),
    [
        pytest.param(
            f"@{SHA} # v7.0.1",
            "@v7",
            f"{JOB} step 1: `uses: actions/checkout@v7` is not pinned to a full commit SHA",
            id="tag-pin",
        ),
        pytest.param(
            f"@{SHA} # v7.0.1",
            f"@{SHA}",
            f"{JOB} step 1: `uses: actions/checkout@{SHA}` has no `# v<version>` comment",
            id="no-version-comment",
        ),
        pytest.param(
            "    timeout-minutes: 10\n",
            "",
            f"{JOB}: no timeout-minutes",
            id="no-timeout",
        ),
        pytest.param(
            "permissions:\n  contents: read\n\nconcurrency",
            "permissions:\n  contents: write\n\nconcurrency",
            f"{W}: top-level permissions must be {{}} or contents: read",
            id="write-permissions",
        ),
        pytest.param(
            "permissions:\n  contents: read\n\nconcurrency",
            "permissions: write-all\n\nconcurrency",
            f"{W}: top-level permissions must be {{}} or contents: read",
            id="shorthand-permissions",
        ),
        pytest.param(
            "permissions:\n  contents: read\n\nconcurrency",
            "concurrency",
            f"{W}: top-level permissions must be {{}} or contents: read",
            id="no-permissions",
        ),
        pytest.param(
            "          persist-credentials: false\n",
            "          fetch-depth: 0\n",
            f"{JOB} step 1: actions/checkout without persist-credentials: false",
            id="checkout-keeps-credentials",
        ),
        pytest.param(
            "  pull_request:\n",
            "  pull_request_target:\n",
            f"{W}: triggers on pull_request_target",
            id="pull-request-target",
        ),
        pytest.param(
            "      - name: Test\n",
            "      - name: Test\n        continue-on-error: true\n",
            f"{JOB} step 3 (Test): `continue-on-error: true` lets a failure pass",
            id="step-continue-on-error",
        ),
        pytest.param(
            "    timeout-minutes: 10\n",
            "    timeout-minutes: 10\n    continue-on-error: ${{ matrix.experimental }}\n",
            f"{JOB}: `continue-on-error: ${{{{ matrix.experimental }}}}` lets a "
            "failure pass",
            id="job-continue-on-error",
        ),
        pytest.param(
            "          uv run pytest\n",
            "          uv run pytest || true\n",
            f"{W}:31: `|| true` swallows a failure",
            id="or-true",
        ),
        pytest.param(
            "  cancel-in-progress: ${{ github.event_name == 'pull_request' }}\n",
            "  cancel-in-progress: true\n",
            f"{W}: `cancel-in-progress: true` can cancel a push run on main",
            id="cancels-push",
        ),
        pytest.param(
            "github.event_name == 'pull_request' && github.ref || github.sha",
            "github.ref",
            f"{W}: concurrency group '${{{{ github.workflow }}}}-${{{{ github.ref }}}}' "
            "is shared by push runs, so a newer push cancels a pending one",
            id="push-group-by-ref",
        ),
        pytest.param(
            "    permissions:\n      pull-requests: write\n",
            "    concurrency: deploy\n",
            f"{JOB}: concurrency group 'deploy' is shared by push runs, so a newer "
            "push cancels a pending one",
            id="job-concurrency",
        ),
    ],
)
def test_hygiene_findings_violation_names_workflow(
    make_workflow: MakeWorkflow, old: str, new: str, finding: str
) -> None:
    assert old in CLEAN

    root = make_workflow(CLEAN.replace(old, new))

    assert hygiene_findings(root) == [finding]


def test_hygiene_findings_pull_request_only_may_cancel(
    make_workflow: MakeWorkflow,
) -> None:
    text = (
        CLEAN.replace("  push:\n    branches: [main]\n", "")
        .replace(
            "github.event_name == 'pull_request' && github.ref || github.sha",
            "github.ref",
        )
        .replace("${{ github.event_name == 'pull_request' }}", "true")
    )

    assert hygiene_findings(make_workflow(text)) == []


def test_hygiene_findings_reusable_workflow_call_needs_pin_not_timeout(
    make_workflow: MakeWorkflow,
) -> None:
    text = (
        "on: pull_request\npermissions: {}\njobs:\n  call:\n"
        "    uses: org/repo/.github/workflows/x.yml@main\n"
    )

    assert hygiene_findings(make_workflow(text)) == [
        f"{W}: job 'call': `uses: org/repo/.github/workflows/x.yml@main` is not "
        "pinned to a full commit SHA"
    ]


def test_hygiene_findings_unreadable_steps_fail_closed(
    make_workflow: MakeWorkflow,
) -> None:
    text = CLEAN.replace("    steps:\n      - uses", "    steps:\n    - uses")

    with pytest.raises(UnreadableYamlError, match=r"w\.yml: cannot read"):
        hygiene_findings(make_workflow(text))
