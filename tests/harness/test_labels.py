"""(e) Every label the repository applies is declared exactly once in labels.yml.

`just labels` creates only what ``.github/labels.yml`` declares, so a label
applied anywhere else and missing there fails the write that applies it (or
GitHub creates it with no colour or description); one declared twice, case
aside (GitHub compares label names case-insensitively), is two conflicting
definitions. Applied labels are read from ``.github/workflows/pr-label.yml``
(``label=<name>`` and literal ``--add-label``/``--label`` values in its
``run:`` steps), each issue form's top-level ``labels``, and each
``.github/dependabot.yml`` update's ``labels`` (Dependabot's default
``dependencies`` when an entry sets none). Each of those files is optional.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.harness._workflows import jobs, read_workflow, steps
from tests.harness._yaml import (
    UnreadableYamlError,
    block_text,
    content_lines,
    mapping,
    scalar_list,
    sequence,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    type MakeRoot = Callable[[dict[str, str]], Path]

REPO_ROOT = Path(__file__).resolve().parents[2]
LABELS = ".github/labels.yml"
PR_LABEL = ".github/workflows/pr-label.yml"
ISSUE_FORMS = ".github/ISSUE_TEMPLATE"
DEPENDABOT = ".github/dependabot.yml"
DEPENDABOT_DEFAULT = "dependencies"

_LABEL_VALUE = r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s;|&)]+)"
_APPLIED = re.compile(rf"(?:(?<![\w-])label=|--(?:add-)?label(?:=|\s+)){_LABEL_VALUE}")


def _load_sync_labels() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sync_labels", REPO_ROOT / "scripts" / "sync_labels.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules while the class body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sync_labels = _load_sync_labels()


def _pr_label_labels(root: Path) -> list[tuple[str, str]]:
    path = root / PR_LABEL
    if not path.is_file():
        return []
    top = read_workflow(path)
    applied = [
        (PR_LABEL, match["value"].strip("\"'"))
        for job in jobs(top, path).values()
        for step in steps(job, path)
        if "run" in step
        for match in _APPLIED.finditer(block_text(step["run"]))
        if "$" not in match["value"]
    ]
    if not applied:
        msg = f"{PR_LABEL}: no `label=<name>` or literal `--add-label` found to check"
        raise UnreadableYamlError(msg)
    return applied


def _issue_form_labels(root: Path) -> list[tuple[str, str]]:
    applied: list[tuple[str, str]] = []
    for path in sorted((root / ISSUE_FORMS).glob("*.y*ml")):
        top = mapping(content_lines(path.read_text(encoding="utf-8")), path)
        if "labels" in top:
            relative = path.relative_to(root).as_posix()
            applied.extend(
                (relative, label) for label in scalar_list(top["labels"], path)
            )
    return applied


def _dependabot_labels(root: Path) -> list[tuple[str, str]]:
    path = root / DEPENDABOT
    if not path.is_file():
        return []
    top = mapping(content_lines(path.read_text(encoding="utf-8")), path)
    applied: list[tuple[str, str]] = []
    for item in sequence(top.get("updates", ("", []))[1], path):
        update = mapping(item, path)
        labels = (
            scalar_list(update["labels"], path)
            if "labels" in update
            else [DEPENDABOT_DEFAULT]
        )
        applied.extend((DEPENDABOT, label) for label in labels)
    return applied


def label_findings(root: Path) -> list[str]:
    """Return each applied label not declared, and each label declared twice."""
    path = root / LABELS
    if not path.is_file():
        return [f"{LABELS} is missing"]
    try:
        declared = [
            label.name
            for label in sync_labels.parse_labels(path.read_text(encoding="utf-8"))
        ]
    except sync_labels.LabelsFileError as exc:
        return [f"{LABELS}: {exc}"]
    counts = Counter(name.casefold() for name in declared)
    findings = [
        f"{LABELS}: {name!r} is declared more than once (case-insensitively)"
        for name in sorted({name for name in declared if counts[name.casefold()] > 1})
    ]
    applied = [
        *_pr_label_labels(root),
        *_issue_form_labels(root),
        *_dependabot_labels(root),
    ]
    findings.extend(
        f"{where}: applies label {label!r}, which {LABELS} does not declare"
        for where, label in sorted(set(applied))
        if label not in declared
    )
    return findings


# --- the repository ---


def test_labels_applied_on_repository_are_declared_once() -> None:
    assert label_findings(REPO_ROOT) == []


def test_pr_label_labels_reads_repository_mapping() -> None:
    labels = {label for _, label in _pr_label_labels(REPO_ROOT)}

    assert {"enhancement", "bug", "chore", "ci", "dependencies"} <= labels


# --- fixtures ---

LABELS_TEXT = """\
- name: bug
  color: d73a4a
  description: "Broken."
- name: dependencies
  color: 0366d6
  description: "Bumps."
- name: "priority: P2"
  color: fbca04
  description: "Normal."
"""

PR_LABEL_TEXT = """\
on: pull_request
jobs:
  label:
    steps:
      - name: Apply label
        run: |
          case "$type" in
            fix) label=bug ;;
            {extra}
          esac
          gh pr edit "$PR_NUMBER" --add-label "$label"
"""


@pytest.fixture
def make_root(tmp_path: Path) -> MakeRoot:
    def make(files: dict[str, str]) -> Path:
        files = {LABELS: LABELS_TEXT, **files}
        for relative, text in files.items():
            (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / relative).write_text(text, encoding="utf-8")
        return tmp_path

    return make


def test_label_findings_declared_labels_pass(make_root: MakeRoot) -> None:
    root = make_root(
        {
            PR_LABEL: PR_LABEL_TEXT.format(extra="deps) label=dependencies ;;"),
            f"{ISSUE_FORMS}/bug.yml": 'name: Bug\nlabels: ["bug", "priority: P2"]\n',
            f"{ISSUE_FORMS}/config.yml": "blank_issues_enabled: false\n",
            DEPENDABOT: "version: 2\nupdates:\n  - package-ecosystem: pip\n",
        }
    )

    assert label_findings(root) == []


@pytest.mark.parametrize(
    ("files", "finding"),
    [
        pytest.param(
            {PR_LABEL: PR_LABEL_TEXT.format(extra="feat) label=enhancement ;;")},
            f"{PR_LABEL}: applies label 'enhancement', which {LABELS} does not declare",
            id="pr-label-case-arm",
        ),
        pytest.param(
            {
                PR_LABEL: PR_LABEL_TEXT.format(
                    extra='docs) gh pr edit 1 --add-label "documentation" ;;'
                )
            },
            f"{PR_LABEL}: applies label 'documentation', which {LABELS} does not "
            "declare",
            id="pr-label-literal-add-label",
        ),
        pytest.param(
            {f"{ISSUE_FORMS}/feature.yml": "name: Feature\nlabels: [enhancement]\n"},
            f"{ISSUE_FORMS}/feature.yml: applies label 'enhancement', which {LABELS} "
            "does not declare",
            id="issue-form-flow-list",
        ),
        pytest.param(
            {f"{ISSUE_FORMS}/feature.yml": "name: F\nlabels:\n  - triage\n"},
            f"{ISSUE_FORMS}/feature.yml: applies label 'triage', which {LABELS} does "
            "not declare",
            id="issue-form-block-list",
        ),
        pytest.param(
            {f"{ISSUE_FORMS}/feature.yml": "name: F\nlabels: bug, triage\n"},
            f"{ISSUE_FORMS}/feature.yml: applies label 'triage', which {LABELS} does "
            "not declare",
            id="issue-form-comma-string",
        ),
        pytest.param(
            {
                DEPENDABOT: "version: 2\nupdates:\n  - package-ecosystem: pip\n"
                "    labels: [python]\n"
            },
            f"{DEPENDABOT}: applies label 'python', which {LABELS} does not declare",
            id="dependabot-labels",
        ),
        pytest.param(
            {LABELS: LABELS_TEXT.replace("dependencies", "deps")},
            f"{DEPENDABOT}: applies label 'dependencies', which {LABELS} does not "
            "declare",
            id="dependabot-default",
        ),
        pytest.param(
            {
                LABELS: LABELS_TEXT
                + '- name: Bug\n  color: d73a4a\n  description: "x"\n'
            },
            f"{LABELS}: 'Bug' is declared more than once (case-insensitively)",
            id="declared-twice-by-case",
        ),
        pytest.param(
            {
                LABELS: LABELS_TEXT
                + '- name: bug\n  color: d73a4a\n  description: "x"\n'
            },
            f"{LABELS}: duplicated label names: ['bug']",
            id="declared-twice",
        ),
    ],
)
def test_label_findings_undeclared_or_duplicate_label_fails(
    make_root: MakeRoot, files: dict[str, str], finding: str
) -> None:
    root = make_root(
        {DEPENDABOT: "version: 2\nupdates:\n  - package-ecosystem: pip\n", **files}
    )

    assert finding in label_findings(root)


def test_label_findings_without_labels_file_fails(tmp_path: Path) -> None:
    assert label_findings(tmp_path) == [f"{LABELS} is missing"]


def test_label_findings_pr_label_without_readable_label_fails_closed(
    make_root: MakeRoot,
) -> None:
    text = PR_LABEL_TEXT.format(extra="").replace("fix) label=bug ;;", "")
    root = make_root({PR_LABEL: text})

    with pytest.raises(UnreadableYamlError, match=r"pr-label\.yml: no `label=<name>`"):
        label_findings(root)
