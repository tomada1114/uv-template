"""Keep local tools, the devcontainer and project CI on one Python baseline."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from tests.harness._workflows import jobs, read_workflow, steps, workflow_files
from tests.harness._yaml import mapping, scalar

REPO_ROOT = Path(__file__).resolve().parents[2]


def python_baseline_findings(root: Path) -> list[str]:
    """Report conflicting baseline versions while allowing inferred tool targets."""
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = config["project"]
    floor = re.fullmatch(r">=(\d+\.\d+)(?:\.0)?", project["requires-python"])
    assert floor is not None, "requires-python must state a readable minimum version"
    expected = floor[1]
    versions = {
        ".python-version": (root / ".python-version")
        .read_text(encoding="utf-8")
        .strip(),
        "mypy": config["tool"]["mypy"]["python_version"],
    }
    classifiers = [
        value.rsplit(" :: ", 1)[1]
        for value in project.get("classifiers", [])
        if re.fullmatch(r"Programming Language :: Python :: \d+\.\d+", value)
    ]
    assert classifiers, "project must declare a Python minor-version classifier"
    versions.update(
        {f"classifier {index}": value for index, value in enumerate(classifiers)}
    )
    target = config.get("tool", {}).get("ruff", {}).get("target-version")
    if target is not None:
        match = re.fullmatch(r"py(\d)(\d+)", target)
        assert match is not None, "Ruff target version is unreadable"
        versions["ruff"] = f"{match[1]}.{match[2]}"
    container = root / ".devcontainer/devcontainer.json"
    if container.is_file():
        image = json.loads(container.read_text(encoding="utf-8"))["image"]
        match = re.search(r"python:(\d+\.\d+)(?:[.-]|$)", image)
        assert match is not None, "devcontainer Python image has no readable version"
        versions["devcontainer"] = match[1]
    for path in workflow_files(root):
        for job_id, job in jobs(read_workflow(path), path).items():
            for index, step in enumerate(steps(job, path)):
                uses = scalar(step.get("uses", ("", []))[0])
                if uses.startswith(("astral-sh/setup-uv@", "actions/setup-python@")):
                    inputs = mapping(step.get("with", ("", []))[1], path)
                    if "python-version" in inputs:
                        versions[f"{path.name}/{job_id}/{index}"] = scalar(
                            inputs["python-version"][0]
                        )
    return [
        f"{site}: Python {value} disagrees with requires-python {expected}"
        for site, value in versions.items()
        if value != expected
    ]


def test_python_baseline_repository_versions_agree() -> None:
    assert python_baseline_findings(REPO_ROOT) == []


@pytest.mark.parametrize(
    "site", ["interpreter", "floor", "classifier", "mypy", "container", "ruff", "ci"]
)
def test_python_baseline_mismatched_version_is_rejected(
    tmp_path: Path, site: str
) -> None:
    files = {
        ".python-version": "3.14\n",
        "pyproject.toml": '[project]\nrequires-python = ">=3.14"\nclassifiers = ["Programming Language :: Python :: 3.14"]\n[tool.mypy]\npython_version = "3.14"\n',
        ".devcontainer/devcontainer.json": '{"image":"mcr.microsoft.com/devcontainers/python:3.14"}',
        ".github/workflows/ci.yml": "jobs:\n  lint:\n    steps:\n      - uses: astral-sh/setup-uv@pin\n",
    }
    if site == "interpreter":
        files[".python-version"] = "3.13\n"
    elif site in {"floor", "classifier", "mypy"}:
        old = {
            "floor": ">=3.14",
            "classifier": "Python :: 3.14",
            "mypy": 'python_version = "3.14"',
        }[site]
        files["pyproject.toml"] = files["pyproject.toml"].replace(
            old, old.replace("3.14", "3.13")
        )
    elif site == "container":
        files[".devcontainer/devcontainer.json"] = files[
            ".devcontainer/devcontainer.json"
        ].replace("3.14", "3.13")
    elif site == "ruff":
        files["pyproject.toml"] += '[tool.ruff]\ntarget-version = "py313"\n'
    else:
        files[".github/workflows/ci.yml"] += (
            '        with:\n          python-version: "3.13"\n'
        )
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert python_baseline_findings(tmp_path)
