"""Tests for scripts/apply_ruleset.py and .github/rulesets/main.json."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
RULESET = REPO_ROOT / ".github" / "rulesets" / "main.json"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "apply_ruleset", REPO_ROOT / "scripts" / "apply_ruleset.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


apply_ruleset = _load_module()


def _rule(ruleset: dict[str, Any], rule_type: str) -> dict[str, Any]:
    matches = [rule for rule in ruleset["rules"] if rule["type"] == rule_type]
    assert len(matches) == 1, rule_type
    rule: dict[str, Any] = matches[0]
    return rule


def _required_contexts() -> list[str]:
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))
    checks = _rule(ruleset, "required_status_checks")["parameters"]
    return [check["context"] for check in checks["required_status_checks"]]


# --- workflow scanning (no YAML dependency: the workflows use a fixed layout) ---

_TOP_KEY = re.compile(r"^(?P<key>[A-Za-z_\"'-]+):")
_JOB_ID = re.compile(r"^  (?P<id>[A-Za-z0-9_-]+):\s*$")
_JOB_NAME = re.compile(r"^    name:\s*(?P<name>.+?)\s*$")
_MATRIX_LIST = re.compile(r"^\s+(?P<key>[A-Za-z0-9_-]+):\s*\[(?P<values>[^\]]*)\]\s*$")
_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.(?P<key>[A-Za-z0-9_-]+)\s*\}\}")


def _sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        if match := _TOP_KEY.match(line):
            current = sections.setdefault(match["key"].strip("\"'"), [])
        elif current is not None:
            current.append(line)
    return sections


def _unfiltered_pull_request(on_lines: list[str]) -> bool:
    in_pr = False
    for line in on_lines:
        if re.match(r"^  \S", line):
            in_pr = line.strip().startswith("pull_request:")
            if in_pr:
                continue
        if in_pr and re.match(r"^    (paths|paths-ignore):", line):
            return False
    return any(line.strip().startswith("pull_request:") for line in on_lines)


def _check_names(job_lines: list[str]) -> set[str]:
    """Resolve a job's check-run names, expanding single-line matrix lists."""
    jobs: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in job_lines:
        if match := _JOB_ID.match(line):
            current = jobs.setdefault(match["id"], [])
        elif current is not None:
            current.append(line)
    names: set[str] = set()
    for job_id, lines in jobs.items():
        name = next(
            (m["name"].strip("\"'") for line in lines if (m := _JOB_NAME.match(line))),
            job_id,
        )
        matrix = {
            m["key"]: [v.strip().strip("\"'") for v in m["values"].split(",")]
            for line in lines
            if (m := _MATRIX_LIST.match(line))
        }
        expanded = [name]
        for key in _MATRIX_REF.findall(name):
            expanded = [
                re.sub(rf"\$\{{\{{\s*matrix\.{key}\s*\}}\}}", value, item)
                for item in expanded
                for value in matrix[key]
            ]
        names.update(expanded)
    return names


def every_pr_check_names(workflows_dir: Path) -> set[str]:
    """Return check names from workflows whose pull_request trigger is unfiltered."""
    names: set[str] = set()
    for path in sorted(workflows_dir.glob("*.yml")):
        sections = _sections(path.read_text(encoding="utf-8"))
        if _unfiltered_pull_request(sections.get("on", [])):
            names |= _check_names(sections.get("jobs", []))
    return names


# --- the JSON ---


def test_ruleset_targets_default_branch_with_empty_bypass() -> None:
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))

    assert ruleset["name"] == "main"
    assert ruleset["target"] == "branch"
    assert ruleset["enforcement"] == "active"
    assert ruleset["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert ruleset["bypass_actors"] == []


def test_ruleset_blocks_deletion_and_force_push_and_requires_pr() -> None:
    ruleset = json.loads(RULESET.read_text(encoding="utf-8"))

    _rule(ruleset, "deletion")
    _rule(ruleset, "non_fast_forward")
    pull_request = _rule(ruleset, "pull_request")["parameters"]
    assert pull_request["required_approving_review_count"] == 0


def test_required_contexts_match_settled_defaults() -> None:
    contexts = _required_contexts()

    assert len(contexts) == len(set(contexts))
    assert set(contexts) == {
        "Lint & Type Check",
        "Coverage",
        "Spell Check",
        "Workflow Security Lint",
        "Validate PR title",
        "Analyze (python)",
        "Analyze (actions)",
        "Dependency Review",
    }
    assert not [c for c in contexts if c.startswith("Test (shard")]


def test_required_contexts_run_on_every_pull_request() -> None:
    available = every_pr_check_names(WORKFLOWS)

    missing = sorted(set(_required_contexts()) - available)

    assert missing == [], f"required contexts not run on every PR: {missing}"


def test_path_filtered_workflow_jobs_are_not_every_pr_checks() -> None:
    available = every_pr_check_names(WORKFLOWS)

    assert "Scan uv.lock" not in available
    assert "Secret Scan (full history)" not in available
    assert {"Analyze (python)", "Analyze (actions)", "Test (shard 1/4)"} <= available


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        ("on:\n  pull_request:\n", True),
        ("on:\n  pull_request:\n    types: [opened]\n", True),
        ("on:\n  pull_request:\n    paths: [uv.lock]\n", False),
        ("on:\n  pull_request:\n    paths-ignore: [docs/**]\n", False),
        ("on:\n  push:\n    paths: [a]\n  pull_request:\n", True),
        ("on:\n  schedule:\n    - cron: '0 0 * * 0'\n", False),
    ],
    ids=["bare", "types", "paths", "paths-ignore", "push-paths-only", "no-pr"],
)
def test_every_pr_check_names_honours_trigger_filters(
    tmp_path: Path, trigger: str, expected: bool
) -> None:
    (tmp_path / "w.yml").write_text(
        f"name: W\n{trigger}\njobs:\n  job:\n    name: Job\n", encoding="utf-8"
    )

    assert ("Job" in every_pr_check_names(tmp_path)) is expected


# --- the script ---


class FakeGh:
    """Stands in for `subprocess.run` at the gh boundary, recording each argv."""

    def __init__(
        self, existing: list[dict[str, Any]], fail_on: str | None = None
    ) -> None:
        self.existing = existing
        self.fail_on = fail_on
        self.calls: list[list[str]] = []
        self.inputs: list[str | None] = []

    def __call__(
        self, argv: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        stdin = kwargs.get("input")
        self.inputs.append(stdin if isinstance(stdin, str) else None)
        joined = " ".join(argv)
        if self.fail_on is not None and self.fail_on in joined:
            return subprocess.CompletedProcess(argv, 1, "", "gh: Not Found (HTTP 404)")
        if argv[1:3] == ["repo", "view"]:
            return subprocess.CompletedProcess(argv, 0, "acme/widget\n", "")
        if "--method" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"id": 42}', "")
        return subprocess.CompletedProcess(argv, 0, json.dumps(self.existing), "")


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> Any:
    def make(existing: list[dict[str, Any]], fail_on: str | None = None) -> FakeGh:
        fake = FakeGh(existing, fail_on)
        monkeypatch.setattr(apply_ruleset.subprocess, "run", fake)
        return fake

    return make


def _methods(fake: FakeGh) -> list[str]:
    return [
        argv[argv.index("--method") + 1] for argv in fake.calls if "--method" in argv
    ]


def test_main_creates_ruleset_when_none_has_its_name(
    fake_gh: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = fake_gh([{"id": 7, "name": "other"}])

    code = apply_ruleset.main([], ruleset_file=RULESET)

    assert code == 0
    assert _methods(fake) == ["POST"]
    assert fake.calls[-1][4] == "repos/acme/widget/rulesets"
    assert json.loads(fake.inputs[-1] or "") == json.loads(RULESET.read_text())
    assert "created: ruleset 'main' id 42" in capsys.readouterr().out


def test_main_updates_existing_ruleset_by_id(fake_gh: Any) -> None:
    fake = fake_gh([{"id": 7, "name": "other"}, {"id": 9, "name": "main"}])

    code = apply_ruleset.main(["--repo", "o/r"], ruleset_file=RULESET)

    assert code == 0
    assert _methods(fake) == ["PUT"]
    assert fake.calls[-1][4] == "repos/o/r/rulesets/9"
    assert not [argv for argv in fake.calls if argv[1:3] == ["repo", "view"]]


@pytest.mark.parametrize("ruleset_id", [None, 3], ids=["create", "update"])
def test_upsert_command_never_deletes(ruleset_id: int | None) -> None:
    command = apply_ruleset.upsert_command("o/r", ruleset_id)

    assert "DELETE" not in [part.upper() for part in command]


def test_main_never_issues_delete(fake_gh: Any) -> None:
    fake = fake_gh([{"id": 1, "name": "main"}, {"id": 2, "name": "main-old"}])

    apply_ruleset.main([], ruleset_file=RULESET)

    assert all("DELETE" not in [p.upper() for p in argv] for argv in fake.calls)


@pytest.mark.parametrize(
    ("content", "detail"),
    [
        ('{"name": "main",}', r"invalid JSON"),
        ("[]", r"top level must be a JSON object"),
        ('{"name": "main", "target": "branch"}', r"missing required keys"),
        (
            '{"name": "", "target": "b", "enforcement": "a", "conditions": {}, "rules": []}',
            r"name must be a non-empty string",
        ),
    ],
    ids=["trailing-comma", "not-object", "missing-keys", "empty-name"],
)
def test_main_rejects_bad_file_before_any_gh_call(
    tmp_path: Path,
    fake_gh: Any,
    capsys: pytest.CaptureFixture[str],
    content: str,
    detail: str,
) -> None:
    fake = fake_gh([])
    path = tmp_path / "main.json"
    path.write_text(content, encoding="utf-8")

    code = apply_ruleset.main([], ruleset_file=path)

    err = capsys.readouterr().err
    assert code == 1
    assert fake.calls == []
    assert re.search(rf"^ERR_RULESET_FILE: .*{detail}", err, re.MULTILINE)
    assert "\nExpected: " in err
    assert "\nNext: " in err


def test_main_reports_missing_file(
    tmp_path: Path, fake_gh: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = fake_gh([])

    code = apply_ruleset.main([], ruleset_file=tmp_path / "absent.json")

    assert code == 1
    assert fake.calls == []
    assert capsys.readouterr().err.startswith("ERR_RULESET_FILE: ")


def test_main_names_human_step_when_gh_denied(
    fake_gh: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_gh([], fail_on="--method")

    code = apply_ruleset.main(["--repo", "o/r"], ruleset_file=RULESET)

    err = capsys.readouterr().err
    assert code == 1
    assert "ERR_RULESET_GH: " in err
    assert "Next: a repository admin runs `just ruleset`" in err


def test_main_reports_gh_failure_resolving_repo(
    fake_gh: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = fake_gh([])

    def broken(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        fake.calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "not a git repository")

    monkeypatch.setattr(apply_ruleset.subprocess, "run", broken)

    code = apply_ruleset.main([], ruleset_file=RULESET)

    err = capsys.readouterr().err
    assert code == 1
    assert "ERR_RULESET_GH: gh repo view" in err
    assert "Next: check `gh auth status`" in err
    assert len(fake.calls) == 1
