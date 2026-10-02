"""Smoke-test built distributions in isolated virtual environments."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_SUFFIXES = (".whl", ".tar.gz")
VALIDATE_IMPORTS_SCRIPT = """
from __future__ import annotations

import importlib
import importlib.metadata as metadata
from pathlib import Path, PurePosixPath
import sys

project_name = sys.argv[1]
repo_root = Path(sys.argv[2]).resolve()
distribution = metadata.distribution(project_name)
files = distribution.files or []
import_names: set[str] = set()

for file in files:
    path = PurePosixPath(str(file))
    root = path.parts[0]

    if root.endswith((".dist-info", ".data")):
        continue

    if len(path.parts) == 1:
        if path.suffix == ".py":
            import_names.add(path.stem)
        continue

    if path.suffix == ".py":
        import_names.add(root)

if not import_names:
    raise SystemExit(
        f"Could not determine any import targets from distribution {project_name!r}."
    )

for import_name in sorted(import_names):
    module = importlib.import_module(import_name)
    module_file = getattr(module, "__file__", None)
    if module_file is None:
        continue

    module_path = Path(module_file).resolve()
    if repo_root in module_path.parents:
        raise SystemExit(
            f"Imported {import_name!r} from the repository tree instead of the "
            f"installed distribution: "
            f"{module_path}"
        )
"""


def _load_project(pyproject_path: Path) -> dict[str, object]:
    """Return the ``[project]`` table from pyproject metadata."""
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject.get("project")
    if not isinstance(project, dict):
        msg = "pyproject.toml is missing a [project] table."
        raise SystemExit(msg)

    return project


def _project_name(project: dict[str, object]) -> str:
    """Return the distribution name declared in pyproject metadata."""
    project_name = project.get("name")
    if not isinstance(project_name, str) or not project_name:
        msg = "pyproject.toml must define a non-empty project.name value."
        raise SystemExit(msg)

    return project_name


def _console_scripts(project: dict[str, object]) -> list[str]:
    """Return the console script names the distribution declares.

    These are what a user actually types after installing, and they only exist
    if the entry point resolves — so running each one is the cheapest proof
    that the artifact installs a working command and not just an importable
    package. A project with no ``[project.scripts]`` table yields an empty
    list, which makes the check a no-op.
    """
    scripts = project.get("scripts", {})
    if not isinstance(scripts, dict):
        msg = "pyproject.toml [project.scripts] must be a table."
        raise SystemExit(msg)

    return sorted(str(name) for name in scripts)


def _artifact_paths(arguments: list[str]) -> list[Path]:
    """Return explicit or auto-detected distribution artifacts to validate."""
    explicit_paths = [Path(argument).resolve() for argument in arguments[1:]]
    if explicit_paths:
        artifacts = explicit_paths
    else:
        dist_dir = REPO_ROOT / "dist"
        if not dist_dir.is_dir():
            msg = "Distribution directory not found: dist/"
            raise SystemExit(msg)
        artifacts = sorted(
            path for path in dist_dir.iterdir() if path.name.endswith(ARTIFACT_SUFFIXES)
        )

    if not artifacts:
        msg = "No wheel or source distribution found in dist/."
        raise SystemExit(msg)
    for artifact in artifacts:
        if not artifact.is_file():
            msg = f"Distribution artifact not found: {artifact}"
            raise SystemExit(msg)
        if not artifact.name.endswith(ARTIFACT_SUFFIXES):
            msg = f"Unsupported distribution artifact: {artifact}"
            raise SystemExit(msg)
    return artifacts


def _venv_executable(venv_dir: Path, name: str) -> Path:
    """Return the path of an executable installed into the temporary venv."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / f"{name}.exe"
    return venv_dir / "bin" / name


def _venv_python(venv_dir: Path) -> Path:
    """Return the Python executable path for the temporary virtual environment."""
    return _venv_executable(venv_dir, "python")


def _run(command: list[str]) -> None:
    """Run a command and fail fast if it exits unsuccessfully."""
    # Commands are passed as fixed argument lists with shell=False.
    subprocess.run(command, check=True, cwd=REPO_ROOT)  # noqa: S603


def _smoke_artifact(
    artifact: Path,
    project_name: str,
    console_scripts: list[str],
) -> None:
    """Install one distribution artifact into a temporary environment."""
    with tempfile.TemporaryDirectory(prefix="package-smoke-test-") as temp_dir:
        venv_dir = Path(temp_dir) / "venv"
        _run(["uv", "venv", "--python", sys.executable, str(venv_dir)])

        venv_python = _venv_python(venv_dir)
        _run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv_python),
                "--no-cache",
                str(artifact),
            ]
        )
        _run(
            [
                str(venv_python),
                "-c",
                VALIDATE_IMPORTS_SCRIPT,
                project_name,
                str(REPO_ROOT),
            ]
        )

        for script_name in console_scripts:
            script_path = _venv_executable(venv_dir, script_name)
            if not script_path.is_file():
                msg = f"The artifact did not install the {script_name!r} command."
                raise SystemExit(msg)
            _run([str(script_path), "--help"])


def main(arguments: list[str]) -> int:
    """Install each built distribution into an isolated environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifacts",
        nargs="*",
        help="Wheel or source distribution paths (defaults to dist/*).",
    )
    parsed = parser.parse_args(arguments[1:])

    project = _load_project(REPO_ROOT / "pyproject.toml")
    project_name = _project_name(project)
    console_scripts = _console_scripts(project)

    for artifact in _artifact_paths([arguments[0], *parsed.artifacts]):
        _smoke_artifact(artifact, project_name, console_scripts)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
