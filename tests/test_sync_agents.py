"""Tests for scripts/sync_agents.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sync_agents", REPO_ROOT / "scripts" / "sync_agents.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules while the class body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sync_agents = _load_module()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_committed_mirror_matches_source() -> None:
    differences = sync_agents.diff_trees(
        REPO_ROOT / sync_agents.SOURCE_DIRECTORY,
        REPO_ROOT / sync_agents.MIRROR_DIRECTORY,
    )

    assert differences == []


def test_diff_trees_reports_missing_differing_and_extra_files(tmp_path: Path) -> None:
    source, mirror = tmp_path / "source", tmp_path / "mirror"
    _write(source / "a" / "SKILL.md", "new")
    _write(source / "b" / "SKILL.md", "same")
    _write(mirror / "a" / "SKILL.md", "old")
    _write(mirror / "b" / "SKILL.md", "same")
    _write(mirror / "c" / "SKILL.md", "stale")
    _write(source / "b" / "scripts" / "__pycache__" / "x.pyc", "bytecode")

    differences = sync_agents.diff_trees(source, mirror)

    assert [(d.kind, d.relative) for d in differences] == [
        ("differs", "a/SKILL.md"),
        ("extra", "c/SKILL.md"),
    ]


def test_sync_trees_makes_mirror_identical_and_prunes_empty_dirs(
    tmp_path: Path,
) -> None:
    source, mirror = tmp_path / "source", tmp_path / "mirror"
    _write(source / "a" / "references" / "x.md", "x")
    _write(mirror / "gone" / "deep" / "SKILL.md", "stale")

    changed = sync_agents.sync_trees(source, mirror)

    assert {d.relative for d in changed} == {"a/references/x.md", "gone/deep/SKILL.md"}
    assert sync_agents.diff_trees(source, mirror) == []
    assert not (mirror / "gone").exists()


def test_list_files_missing_directory_is_empty(tmp_path: Path) -> None:
    assert sync_agents.list_files(tmp_path / "absent", "absent") == []


def test_list_files_refuses_symlinked_entry(tmp_path: Path) -> None:
    _write(tmp_path / "real.md", "x")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "link.md").symlink_to(tmp_path / "real.md")

    with pytest.raises(sync_agents.SyncAgentsError, match=r"neither a file"):
        sync_agents.list_files(tmp_path / "skills", "skills")


def test_list_files_refuses_symlinked_root(tmp_path: Path) -> None:
    (tmp_path / "real").mkdir()
    (tmp_path / "skills").symlink_to(tmp_path / "real")

    with pytest.raises(sync_agents.SyncAgentsError, match=r"is a symlink"):
        sync_agents.list_files(tmp_path / "skills", "skills")


def test_main_check_exits_one_on_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / sync_agents.SOURCE_DIRECTORY / "a" / "SKILL.md", "x")

    assert sync_agents.main(["--check"], root=tmp_path) == 1
    assert "ERR_AGENTS_DRIFT" in capsys.readouterr().err


def test_main_sync_then_check_passes(tmp_path: Path) -> None:
    _write(tmp_path / sync_agents.SOURCE_DIRECTORY / "a" / "SKILL.md", "x")

    assert sync_agents.main([], root=tmp_path) == 0
    assert sync_agents.main(["--check"], root=tmp_path) == 0


def test_main_reports_unsupported_entry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".agents").mkdir()
    (tmp_path / "real").mkdir()
    (tmp_path / sync_agents.SOURCE_DIRECTORY).symlink_to(tmp_path / "real")

    assert sync_agents.main(["--check"], root=tmp_path) == 1
    assert "ERR_AGENTS_UNSUPPORTED_ENTRY" in capsys.readouterr().err
