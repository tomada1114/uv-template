"""Tests for scripts/check_staged.py, the pre-commit layer's secret gate.

Every repository here is a real one under `tmp_path`, driven by the `git`
binary, with the user's and the system's git configuration switched off.
Secret-shaped fixtures are assembled at runtime by `_secret`, so this file
never matches a pattern itself -- and the gate does not refuse its own tests.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_staged.py"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
HOOK_ID = "check-staged"
BLOCKED = 1
GIT_FAILED = 2


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_staged", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their module through sys.modules while the class body runs.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_staged = _load_module()


def _secret(*parts: str) -> str:
    """Join fragments into a secret-shaped string no source line contains."""
    return "".join(parts)


def _aws_key() -> str:
    return _secret("AK", "IA", "Q" * 16)


SECRET_SAMPLES = {
    "AWS access key": _aws_key(),
    "GitHub token": _secret("gh", "p_", "a" * 36),
    "GitHub fine-grained token": _secret("github", "_pat_", "A" * 22, "_", "b" * 59),
    "Anthropic API key": _secret("sk-", "ant-", "api03-", "x" * 40),
    "OpenAI project key": _secret("sk-", "proj-", "y" * 40),
    "OpenRouter API key": _secret("sk-", "or-", "v1-", "0" * 64),
    "Slack token": _secret("xo", "xb-", "1234567890-abcdefghij"),
    "Stripe live secret key": _secret("sk_", "live_", "Z" * 24),
    "private key": _secret("-----BEGIN ", "OPENSSH PRIVATE", " KEY-----"),
}


@dataclass(frozen=True, slots=True)
class GitRepo:
    """A throwaway repository and the environment every command runs with."""

    root: Path
    env: dict[str, str]

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ["git", *args],  # noqa: S607 -- git from PATH, as the hook runs it
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=check,
        )

    def write(self, relative: str, content: str | bytes) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    def stage(self, relative: str, content: str | bytes) -> None:
        self.write(relative, content)
        self.git("add", "--", relative)

    def commit_all(self, message: str) -> None:
        self.git("add", "--all")
        self.git("commit", "--quiet", "-m", message)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").stdout.strip()

    def run_check(
        self, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            [sys.executable, str(SCRIPT)],
            cwd=self.root,
            env=env or self.env,
            capture_output=True,
            text=True,
            check=False,
        )


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    """Return an environment free of the caller's git state and configuration."""
    env = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="Test",
        GIT_COMMITTER_EMAIL="test@example.com",
        GIT_EDITOR="true",
        PRE_COMMIT_HOME=str(tmp_path / "pre-commit-home"),
    )
    env.pop("PRE_COMMIT", None)
    return env


@pytest.fixture
def make_repo(tmp_path: Path) -> Callable[..., GitRepo]:
    """Return a factory for repositories, with or without a first commit."""

    def factory(*, with_commit: bool = True) -> GitRepo:
        root = tmp_path / "repo"
        root.mkdir()
        repo = GitRepo(root, _isolated_env(tmp_path))
        repo.git("init", "--quiet", "--initial-branch=main")
        if with_commit:
            repo.write("README.md", "hello\n")
            repo.commit_all("initial")
        return repo

    return factory


def _load_pre_commit_config() -> dict[str, object]:
    # pre-commit depends on PyYAML, so it is present wherever the hook runs;
    # it ships no type stubs, hence the dynamic import.
    yaml = importlib.import_module("yaml")
    config: dict[str, object] = yaml.safe_load(
        PRE_COMMIT_CONFIG.read_text(encoding="utf-8")
    )
    return config


def _all_hooks(config: dict[str, object]) -> list[dict[str, object]]:
    repos = config["repos"]
    assert isinstance(repos, list)
    return [hook for repo in repos for hook in repo["hooks"]]


def _check_staged_hook(config: dict[str, object]) -> dict[str, object]:
    (hook,) = [hook for hook in _all_hooks(config) if hook["id"] == HOOK_ID]
    return hook


def _install_pre_commit(repo: GitRepo) -> None:
    """Install the real check-staged hook definition into `repo` via pre-commit.

    Only how it is launched changes: `language: python` would build a
    virtualenv per test (and download its build backend), so the script runs
    under the test's own interpreter instead.
    `test_pre_commit_config_runs_the_gate_on_every_commit_kind` pins the real
    language and entry.
    """
    config = _load_pre_commit_config()
    hook = {
        **_check_staged_hook(config),
        "language": "system",
        "entry": f"{shlex.quote(sys.executable)} {shlex.quote(str(SCRIPT))}",
    }
    test_config = {
        "default_install_hook_types": config["default_install_hook_types"],
        "repos": [{"repo": "local", "hooks": [hook]}],
    }
    # JSON is valid YAML, so no YAML writer is needed.
    repo.write(".pre-commit-config.yaml", json.dumps(test_config, indent=2))
    repo.commit_all("add pre-commit config")
    subprocess.run(
        [sys.executable, "-m", "pre_commit", "install"],
        cwd=repo.root,
        env=repo.env,
        capture_output=True,
        check=True,
    )


# --------------------------------------------------------------------------- #
#  Path and content rules
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(".env", "ENV_FILE", id="env"),
        pytest.param(".env.local", "ENV_FILE", id="env-local"),
        pytest.param("app/.env.production", "ENV_FILE", id="nested-env"),
        pytest.param(".ENV", "ENV_FILE", id="env-upper-case"),
        pytest.param(".envrc", "DIRENV_FILE", id="envrc"),
        pytest.param(".envrc.private", "DIRENV_FILE", id="envrc-variant"),
        pytest.param(".envrc.local", "DIRENV_FILE", id="envrc-local"),
        pytest.param(".env.example.local", "ENV_FILE", id="env-example-not-last"),
        pytest.param(".env.sampler", "ENV_FILE", id="env-sample-prefix-only"),
        pytest.param("secrets/token.txt", "SECRETS_DIRECTORY", id="secrets-root"),
        pytest.param("deploy/secrets/db.yml", "SECRETS_DIRECTORY", id="secrets-nested"),
        pytest.param("server.pem", "KEY_FILE", id="pem"),
        pytest.param("tls/server.KEY", "KEY_FILE", id="key-upper-case"),
        pytest.param("id_rsa", "SSH_KEY", id="id-rsa"),
        pytest.param("keys/id_rsa.pub", "SSH_KEY", id="id-rsa-pub"),
        pytest.param(
            ".claude/settings.local.json", "PERSONAL_SETTINGS", id="claude-local"
        ),
        pytest.param(
            "apps/web/.claude/settings.local.json",
            "PERSONAL_SETTINGS",
            id="nested-claude-local",
        ),
        pytest.param(".codex/rules/local.rules", "PERSONAL_SETTINGS", id="codex-local"),
    ],
)
def test_blocked_path_reason_secret_shaped_path_is_refused(
    path: str, expected: str
) -> None:
    assert check_staged.blocked_path_reason(path) is check_staged.BlockedPath[expected]


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(".env.example", id="env-example"),
        pytest.param("config/.env.example", id="nested-env-example"),
        pytest.param(".env.sample", id="env-sample"),
        pytest.param(".env.template", id="env-template"),
        pytest.param(".env.test.example", id="env-variant-example"),
        pytest.param("config/.ENV.SAMPLE", id="env-sample-upper-case"),
        pytest.param(".envrc.example", id="envrc-example"),
        pytest.param(".environment", id="env-prefix-only"),
        pytest.param("src/env.py", id="env-module"),
        pytest.param("docs/secrets.md", id="secrets-file-not-directory"),
        pytest.param("src/secretsmanager.py", id="secrets-prefix"),
        pytest.param("monkey.py", id="key-substring"),
        pytest.param("docs/rotating-id_rsa.md", id="id-rsa-not-prefix"),
        pytest.param(".claude/settings.json", id="claude-shared-settings"),
        pytest.param(
            "nested/.claude/settings.local.json.example", id="settings-example"
        ),
    ],
)
def test_blocked_path_reason_ordinary_path_is_allowed(path: str) -> None:
    assert check_staged.blocked_path_reason(path) is None


@pytest.mark.parametrize(
    ("label", "sample"), SECRET_SAMPLES.items(), ids=SECRET_SAMPLES.keys()
)
def test_secret_kind_credential_shape_is_named(label: str, sample: str) -> None:
    content = f"token = {sample}\n".encode()

    assert check_staged.secret_kind(content) == label


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"", id="empty"),
        pytest.param(
            b"ghp_ github_pat_ sk-ant- sk-proj- sk-or- sk_live_ xoxb-\n",
            id="bare-prefixes",
        ),
        pytest.param(b"-----BEGIN PUBLIC KEY-----\n", id="public-key"),
        pytest.param(
            b"weigh the risk-or-reward-tradeoff-analysis\n", id="risk-or-prose"
        ),
        pytest.param(b"xoxo-gossip-girl-season-finale\n", id="xoxo-prose"),
        pytest.param(b"see desk-proj-overview-for-the-quarter\n", id="desk-proj-prose"),
        pytest.param(SCRIPT.read_bytes(), id="the-gate-itself"),
    ],
)
def test_secret_kind_text_without_credentials_is_none(content: bytes) -> None:
    assert check_staged.secret_kind(content) is None


def test_secret_kind_non_utf8_blob_is_skipped() -> None:
    content = b"\xff\xfe" + _aws_key().encode()

    assert check_staged.secret_kind(content) is None


# --------------------------------------------------------------------------- #
#  The script against a real index
# --------------------------------------------------------------------------- #


def test_check_nothing_staged_exits_zero(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()

    result = repo.run_check()

    assert (result.returncode, result.stderr) == (0, "")


def test_check_clean_change_exits_zero(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    repo.stage("src/app.py", "print('hello')\n")

    assert repo.run_check().returncode == 0


def test_check_env_file_is_refused_by_name(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    repo.stage(".env.local", "harmless\n")

    result = repo.run_check()

    assert result.returncode == BLOCKED
    assert "refused .env.local: an environment file" in result.stderr


def test_check_env_example_passes(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    repo.stage(".env.example", "API_KEY=\n")

    assert repo.run_check().returncode == 0


def test_check_env_sample_passes(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    repo.stage(".env.sample", "API_KEY=\n")

    assert repo.run_check().returncode == 0


def test_check_secret_content_names_file_and_kind_but_not_value(
    make_repo: Callable[..., GitRepo],
) -> None:
    repo = make_repo()
    repo.stage("src/x.py", f"KEY = '{_aws_key()}'\n")

    result = repo.run_check()

    assert result.returncode == BLOCKED
    assert (
        "refused src/x.py: content matches the AWS access key pattern" in result.stderr
    )
    assert _aws_key() not in result.stderr + result.stdout


def test_check_reports_every_finding_in_index_order(
    make_repo: Callable[..., GitRepo],
) -> None:
    repo = make_repo()
    repo.stage(".env", "x\n")
    repo.stage("a.txt", SECRET_SAMPLES["GitHub token"])
    repo.stage("b.txt", "clean\n")

    result = repo.run_check()

    refused = [line for line in result.stderr.splitlines() if "refused" in line]
    assert result.returncode == BLOCKED
    assert [line.split(":")[1].strip() for line in refused] == [
        "refused .env",
        "refused a.txt",
    ]


@pytest.mark.parametrize(
    ("staged", "worktree", "expected"),
    [
        pytest.param("clean\n", _aws_key(), 0, id="unstaged-secret-ignored"),
        pytest.param(_aws_key(), "clean\n", BLOCKED, id="staged-secret-refused"),
    ],
)
def test_check_judges_the_index_not_the_worktree(
    make_repo: Callable[..., GitRepo],
    staged: str,
    worktree: str,
    expected: int,
) -> None:
    repo = make_repo()
    repo.stage("notes.txt", staged)
    repo.write("notes.txt", worktree)

    assert repo.run_check().returncode == expected


def test_check_deleting_a_secret_file_passes(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    repo.write(".env", "TOKEN=1\n")
    repo.commit_all("committed before the gate existed")
    repo.git("rm", "--quiet", "--cached", ".env")

    assert repo.run_check().returncode == 0


def test_check_binary_blob_does_not_crash(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    repo.stage("image.bin", b"\x89PNG\r\n\x1a\n\xff" + _aws_key().encode())

    result = repo.run_check()

    assert (result.returncode, result.stderr) == (0, "")


def test_check_submodule_entry_is_not_read(make_repo: Callable[..., GitRepo]) -> None:
    repo = make_repo()
    commit = repo.head()
    repo.git("update-index", "--add", "--cacheinfo", f"160000,{commit},vendor/lib")

    assert repo.run_check().returncode == 0


@pytest.mark.parametrize(
    ("relative", "content", "expected"),
    [
        pytest.param("a.txt", "clean\n", 0, id="clean"),
        pytest.param("a.txt", _aws_key(), BLOCKED, id="secret"),
    ],
)
def test_check_first_commit_on_unborn_branch_is_judged(
    make_repo: Callable[..., GitRepo],
    relative: str,
    content: str,
    expected: int,
) -> None:
    repo = make_repo(with_commit=False)
    repo.stage(relative, content)

    assert repo.run_check().returncode == expected


def test_check_outside_a_repository_fails_closed(tmp_path: Path) -> None:
    outside = tmp_path / "plain"
    outside.mkdir()

    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell
        [sys.executable, str(SCRIPT)],
        cwd=outside,
        env=_isolated_env(tmp_path) | {"GIT_CEILING_DIRECTORIES": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == GIT_FAILED
    assert result.stderr.startswith("check_staged: `git ")


def test_check_reads_all_blobs_with_one_cat_file_batch(
    make_repo: Callable[..., GitRepo],
    tmp_path: Path,
) -> None:
    real_git = shutil.which("git")
    assert real_git is not None
    log = tmp_path / "git-calls.log"
    wrapper_dir = tmp_path / "bin"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "git"
    wrapper.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "$*" >> {shlex.quote(str(log))}\n'
        f'exec {shlex.quote(real_git)} "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    repo = make_repo()
    for name in ("a.txt", "b.txt", "c.txt"):
        repo.stage(name, f"{name}\n")
    repo.stage("d.txt", _aws_key())
    env = repo.env | {"PATH": f"{wrapper_dir}{os.pathsep}{repo.env['PATH']}"}

    result = repo.run_check(env)

    calls = log.read_text(encoding="utf-8").splitlines()
    assert result.returncode == BLOCKED
    assert [call for call in calls if call.startswith("cat-file")] == [
        "cat-file --batch"
    ]


# --------------------------------------------------------------------------- #
#  The hook as installed by pre-commit, on every kind of commit
# --------------------------------------------------------------------------- #


def test_pre_commit_config_runs_the_gate_on_every_commit_kind() -> None:
    config = _load_pre_commit_config()
    hook = _check_staged_hook(config)
    hook_types, stages = config["default_install_hook_types"], hook["stages"]

    assert isinstance(hook_types, list)
    assert isinstance(stages, list)
    assert {"pre-commit", "pre-merge-commit"} <= set(hook_types)
    assert {"pre-commit", "pre-merge-commit"} <= set(stages)
    assert (hook["always_run"], hook["pass_filenames"]) == (True, False)
    assert not {"files", "exclude", "types", "types_or"} & hook.keys()


def test_pre_commit_config_runs_the_gate_without_uv() -> None:
    hook = _check_staged_hook(_load_pre_commit_config())

    assert (hook["language"], hook["entry"]) == (
        "python",
        "python scripts/check_staged.py",
    )
    assert "additional_dependencies" not in hook


def test_pre_commit_config_only_the_gate_runs_at_pre_merge_commit() -> None:
    # A hook's manifest may declare stages of its own (typos lists
    # pre-merge-commit), which `default_stages` would not override, so every
    # other hook must name its stages explicitly.
    others = [
        hook for hook in _all_hooks(_load_pre_commit_config()) if hook["id"] != HOOK_ID
    ]

    assert others
    assert {str(hook["id"]): hook.get("stages") for hook in others} == {
        str(hook["id"]): ["pre-commit"] for hook in others
    }


@pytest.fixture
def hooked_repo(make_repo: Callable[..., GitRepo]) -> GitRepo:
    """Return a committed repository with the check-staged hook installed."""
    repo = make_repo()
    repo.write("shared.txt", "base\n")
    repo.commit_all("base")
    _install_pre_commit(repo)
    return repo


def test_ordinary_commit_with_secret_is_refused(hooked_repo: GitRepo) -> None:
    before = hooked_repo.head()
    hooked_repo.stage(".env.local", "TOKEN=1\n")

    result = hooked_repo.git("commit", "-m", "leak", check=False)

    assert result.returncode != 0
    assert "refused .env.local" in result.stdout + result.stderr
    assert hooked_repo.head() == before


def test_ordinary_commit_of_env_example_passes(hooked_repo: GitRepo) -> None:
    before = hooked_repo.head()
    hooked_repo.stage(".env.example", "TOKEN=\n")

    hooked_repo.git("commit", "--quiet", "-m", "example")

    assert hooked_repo.head() != before


def test_commit_with_pathspec_judges_the_temporary_index(hooked_repo: GitRepo) -> None:
    before = hooked_repo.head()
    hooked_repo.write("shared.txt", f"{_aws_key()}\n")

    result = hooked_repo.git("commit", "-m", "leak", "--", "shared.txt", check=False)

    assert result.returncode != 0
    assert (
        "refused shared.txt: content matches the AWS access key pattern"
        in result.stdout + result.stderr
    )
    assert hooked_repo.head() == before


def _commit_on_side_branch(repo: GitRepo, relative: str, content: str) -> None:
    """Commit `content` on a new `side` branch, past the hook, then return to main."""
    repo.git("switch", "--quiet", "-c", "side")
    repo.write(relative, content)
    repo.git("add", "--", relative)
    repo.git("commit", "--quiet", "--no-verify", "-m", "side")
    repo.git("switch", "--quiet", "main")


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        pytest.param("config.txt", f"{_aws_key()}\n", id="secret-content"),
        pytest.param(".env", "TOKEN=1\n", id="secret-path"),
    ],
)
def test_clean_merge_of_content_already_in_the_other_history_passes(
    hooked_repo: GitRepo,
    relative: str,
    content: str,
) -> None:
    _commit_on_side_branch(hooked_repo, relative, content)
    before = hooked_repo.head()

    hooked_repo.git("merge", "--quiet", "--no-ff", "--no-edit", "side")

    assert hooked_repo.head() != before
    assert (
        hooked_repo.git("rev-parse", "HEAD^2").stdout
        == hooked_repo.git("rev-parse", "side").stdout
    )


def test_clean_merge_producing_new_secret_content_is_refused(
    hooked_repo: GitRepo,
) -> None:
    # Both sides edit shared.txt in different places, so the merged blob is
    # new to both histories and is judged at pre-merge-commit.
    hooked_repo.write("shared.txt", "top\nmiddle\nbottom\n")
    hooked_repo.commit_all("three lines")
    _commit_on_side_branch(hooked_repo, "shared.txt", f"{_aws_key()}\nmiddle\nbottom\n")
    hooked_repo.write("shared.txt", "top\nmiddle\nmain\n")
    hooked_repo.commit_all("main edits the bottom")
    before = hooked_repo.head()

    result = hooked_repo.git("merge", "--no-ff", "--no-edit", "side", check=False)

    assert result.returncode != 0
    assert "refused shared.txt" in result.stdout + result.stderr
    assert hooked_repo.head() == before


def test_merge_adding_new_secret_content_is_refused_with_merge_hint(
    hooked_repo: GitRepo,
) -> None:
    _commit_on_side_branch(hooked_repo, "side.txt", "harmless\n")
    hooked_repo.git("merge", "--quiet", "--no-ff", "--no-commit", "side")
    hooked_repo.stage("added-during-merge.txt", f"{_aws_key()}\n")
    before = hooked_repo.head()

    result = hooked_repo.git("commit", "--no-edit", check=False)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "refused added-during-merge.txt" in output
    assert "refused side.txt" not in output
    assert "A merge is in progress" in output
    assert hooked_repo.head() == before


def _diverge_on_shared_file(repo: GitRepo) -> None:
    """Commit conflicting edits to shared.txt on `side` and on `main`."""
    repo.git("switch", "--quiet", "-c", "side")
    repo.write("shared.txt", "side\n")
    repo.git("commit", "--quiet", "-am", "side")
    repo.git("switch", "--quiet", "main")
    repo.write("shared.txt", "main\n")
    repo.git("commit", "--quiet", "-am", "main")


def test_conflicted_merge_resolution_with_secret_is_refused(
    hooked_repo: GitRepo,
) -> None:
    _diverge_on_shared_file(hooked_repo)
    before = hooked_repo.head()
    assert hooked_repo.git("merge", "side", check=False).returncode != 0
    hooked_repo.stage("shared.txt", f"resolved\n{_aws_key()}\n")

    result = hooked_repo.git("commit", "--no-edit", check=False)

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "refused shared.txt" in output
    assert "A merge is in progress" in output
    assert hooked_repo.head() == before


def test_conflicted_merge_keeps_content_already_in_the_other_history(
    hooked_repo: GitRepo,
) -> None:
    _commit_on_side_branch(hooked_repo, "config.txt", f"{_aws_key()}\n")
    hooked_repo.git("switch", "--quiet", "side")
    hooked_repo.write("shared.txt", "side\n")
    hooked_repo.git("commit", "--quiet", "--no-verify", "-am", "side edit")
    hooked_repo.git("switch", "--quiet", "main")
    hooked_repo.write("shared.txt", "main\n")
    hooked_repo.git("commit", "--quiet", "-am", "main edit")
    assert hooked_repo.git("merge", "side", check=False).returncode != 0
    hooked_repo.stage("shared.txt", "resolved\n")
    before = hooked_repo.head()

    hooked_repo.git("commit", "--quiet", "--no-edit")

    assert hooked_repo.head() != before


def test_commit_at_a_rebase_stop_with_secret_is_refused(hooked_repo: GitRepo) -> None:
    _diverge_on_shared_file(hooked_repo)
    hooked_repo.git("switch", "--quiet", "side")
    assert hooked_repo.git("rebase", "main", check=False).returncode != 0
    before = hooked_repo.head()
    hooked_repo.stage("shared.txt", f"resolved\n{_aws_key()}\n")

    result = hooked_repo.git("commit", "--no-edit", check=False)

    assert result.returncode != 0
    assert "refused shared.txt" in result.stdout + result.stderr
    assert hooked_repo.head() == before
