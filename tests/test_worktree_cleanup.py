"""Tests for the explicit, preview-first worktree cleanup command."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

    import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "worktree_cleanup.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("worktree_cleanup", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_preview_is_default_and_forwards_only_named_branches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_module()
    root = tmp_path / "worktrees"
    root.mkdir()
    helper = tmp_path / "cleanup_run.sh"
    helper.write_text("#!/bin/bash\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(
        command: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(list(command), 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.main(
        ["--root", str(root), "--branch", "codex/123-example"],
        cleanup_script=helper,
    )

    assert result == 0
    assert Path(calls[0][0]).name == "git"
    assert calls[0][1:] == ["check-ref-format", "--branch", "codex/123-example"]
    assert Path(calls[1][0]).name == "bash"
    assert calls[1][1:] == [
        str(helper),
        "--worktree-root",
        str(root.resolve()),
        "--merged-only",
        "--branch",
        "codex/123-example",
        "--dry-run",
    ]
    assert "Dry run only" in capsys.readouterr().out


def test_apply_requires_an_explicit_scope_and_omits_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_module()
    root = tmp_path / "worktrees"
    root.mkdir()
    helper = tmp_path / "cleanup_run.sh"
    helper.write_text("#!/bin/bash\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(
        command: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(list(command), 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.main(
        ["--root", str(root), "--branch", "codex/123-example", "--apply"],
        cleanup_script=helper,
    )

    assert result == 0
    assert Path(calls[-1][0]).name == "bash"
    assert "--branch" in calls[-1][1:]
    assert "codex/123-example" in calls[-1][1:]
    assert "--dry-run" not in calls[-1][1:]
    assert "Ignored files" in capsys.readouterr().out


def test_missing_root_fails_before_running_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_module()
    helper = tmp_path / "cleanup_run.sh"
    helper.write_text("#!/bin/bash\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(
        command: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(list(command), 0, "", "")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.main(
        ["--root", str(tmp_path / "missing"), "--branch", "codex/123-example"],
        cleanup_script=helper,
    )

    assert result == 2
    assert calls == []
    assert "ERR_WORKTREE_ROOT" in capsys.readouterr().err


def test_invalid_branch_fails_before_running_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _load_module()
    root = tmp_path / "worktrees"
    root.mkdir()
    helper = tmp_path / "cleanup_run.sh"
    helper.write_text("#!/bin/bash\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(
        command: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(list(command), 1, "", "invalid ref")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.main(
        ["--root", str(root), "--branch", "bad..branch"],
        cleanup_script=helper,
    )

    assert result == 2
    assert len(calls) == 1
    assert Path(calls[0][0]).name == "git"
    assert calls[0][1:] == ["check-ref-format", "--branch", "bad..branch"]
    assert "ERR_WORKTREE_BRANCH" in capsys.readouterr().err
