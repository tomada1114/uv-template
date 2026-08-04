"""Tests for scripts/bootstrap.py."""

from __future__ import annotations

import datetime as dt
import importlib.util
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDERS = (
    "my-package",
    "my_package",
    "your-username",
    "Your Name",
    "you@example.com",
    "uv-template",
    "A short description of the project.",
    "A short description of what this library does.",
)
SELF_DELETED = (
    "TEMPLATE.md",
    "scripts/bootstrap.py",
    "tests/test_bootstrap.py",
)


def _load_bootstrap_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "bootstrap", REPO_ROOT / "scripts" / "bootstrap.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_tracked_files(destination: Path) -> None:
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(REPO_ROOT), "ls-files"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    )
    for relative_path in result.stdout.splitlines():
        source = REPO_ROOT / relative_path
        if not source.is_file():
            continue
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


@pytest.fixture
def template_copy(tmp_path, monkeypatch):
    """A copy of the tracked template tree, isolated from the real repo.

    ``REPO_ROOT`` is repointed at the copy so a test that exercises ``main()``
    can never rewrite the checkout it runs from.
    """
    _copy_tracked_files(tmp_path)
    module = _load_bootstrap_module()
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    return tmp_path, module


def _bootstrap_into(root, bootstrap, **overrides):
    """Run a fully specified bootstrap against a copy of the template."""
    kwargs = {
        "package_name": "acme-widgets",
        "author": "Ada Lovelace",
        "email": "ada@example.com",
        "github_user": "ada",
        "description": "Widgets for the acme use case.",
    }
    kwargs.update(overrides)
    return bootstrap.bootstrap(root, **kwargs)


def test_bootstrap_replaces_all_placeholders(template_copy):
    root, bootstrap = template_copy

    module_name = _bootstrap_into(root, bootstrap)

    assert module_name == "acme_widgets"
    assert (root / "src" / "acme_widgets").is_dir()
    assert not (root / "src" / "my_package").exists()

    for path in root.rglob("*"):
        if not path.is_file() or path.name == "uv.lock":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for placeholder in PLACEHOLDERS:
            assert placeholder not in text, f"{placeholder!r} still present in {path}"


def test_bootstrap_writes_the_description_everywhere(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap, description="Widgets that never jam.")

    for relative_path in ("pyproject.toml", "mkdocs.yml", "README.md"):
        text = (root / relative_path).read_text(encoding="utf-8")
        assert "Widgets that never jam." in text, relative_path


def test_bootstrap_renames_the_devcontainer(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap)

    devcontainer = (root / ".devcontainer" / "devcontainer.json").read_text(
        encoding="utf-8"
    )
    assert '"name": "acme-widgets"' in devcontainer


def test_bootstrap_writes_the_current_year_into_the_license(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap)

    year = dt.datetime.now(tz=dt.UTC).year
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    assert f"Copyright (c) {year} Ada Lovelace" in license_text


def test_bootstrap_moves_exclude_newer_to_two_weeks_ago(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap)

    cutoff = dt.datetime.now(tz=dt.UTC).date() - dt.timedelta(days=14)
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert f'exclude-newer = "{cutoff.isoformat()}T00:00:00Z"' in pyproject


def test_bootstrap_resets_the_changelog(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap)

    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.rstrip().endswith("## [Unreleased]")
    assert "Keep a Changelog" in changelog
    assert "Initial project structure" not in changelog


def test_bootstrap_deletes_its_own_scaffolding(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap)

    for relative_path in SELF_DELETED:
        assert not (root / relative_path).exists(), relative_path


def test_bootstrap_keeps_its_scaffolding_when_asked(template_copy):
    root, bootstrap = template_copy

    _bootstrap_into(root, bootstrap, keep_bootstrap=True)

    for relative_path in SELF_DELETED:
        assert (root / relative_path).is_file(), relative_path


def test_bootstrap_requires_a_github_user(template_copy):
    root, bootstrap = template_copy

    with pytest.raises(SystemExit):
        bootstrap.main(["acme-widgets"])

    # The run must abort before touching anything.
    assert (root / "src" / "my_package").is_dir()


def test_bootstrap_rejects_invalid_package_name(template_copy):
    root, bootstrap = template_copy

    with pytest.raises(SystemExit):
        _bootstrap_into(root, bootstrap, package_name="1-invalid-name")
