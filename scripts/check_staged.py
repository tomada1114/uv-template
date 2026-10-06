"""Refuse a commit that would put a secret into history, judged from the index.

This is the secret gate of the pre-commit layer (`.pre-commit-config.yaml`,
hook id `check-staged`). It runs on `git commit` itself, so it holds for every
author -- a human, Claude Code, Codex CLI, or any other tool -- rather than only
for the agent whose hook configuration happened to be loaded.

The scope is deliberately narrow: a secret-shaped path (`.env`, `secrets/**`,
a key file, a personal agent settings file) or credential-shaped content in a
staged file. Anything else a commit might do is a judgement call that belongs
in the pull request. A hook that refuses legitimate work teaches its author to
reach for `--no-verify`, which switches this check off along with the rest.

Each staged path is judged in two phases: the path first, then -- only when the
path passes -- the staged blob. Blobs are read by id from the index through one
`git cat-file --batch` process for the whole run, so a partially staged file is
judged exactly as it will be committed, and a refused path's content is never
read. Output names the path and the rule, never the matched text.

Deletions are not inspected: removing a file cannot add a secret, and refusing
it would block the very commit that removes one. Git runs with the inherited
environment on purpose: `git commit -a` and `git commit -- <path>` hand the hook
a temporary index through `GIT_INDEX_FILE`, and that index is what is committed.

Usage:
    uv run --locked python scripts/check_staged.py

Exit codes:
    0  nothing staged is refused (including when nothing is staged)
    1  a staged path or staged content was refused
    2  git could not list or read the staged changes
"""

from __future__ import annotations

import argparse
import enum
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

# A submodule entry names a commit in another repository; there is no blob here.
GITLINK_MODE: Final = "160000"
# `--no-renames` reports a rename as a deletion plus an addition, so every
# entry carries exactly one path; deletions (D) are left out on purpose.
STAGED_STATUS_FILTER: Final = "ACMT"
RAW_FIELDS_PER_ENTRY: Final = 2
RAW_META_WORDS: Final = 5
BATCH_HEADER_WORDS: Final = 3
BLOB_TYPE: Final = "blob"
FRAME_TERMINATOR: Final = b"\n"

ENV_FILE_NAME: Final = ".env"
ENV_EXAMPLE_NAME: Final = ".env.example"
DIRENV_FILE_NAME: Final = ".envrc"
SECRETS_DIRECTORY: Final = "secrets"
KEY_FILE_SUFFIXES: Final = (".pem", ".key")
SSH_KEY_PREFIX: Final = "id_rsa"
PERSONAL_SETTINGS_PATHS: Final = frozenset(
    {".claude/settings.local.json", ".codex/rules/local.rules"},
)

FIX_HINT: Final = (
    "Remove the secret from the file and `git add` it again, or take the path "
    "out of the index with `git rm --cached <path>` and list it in .gitignore. "
    "Never bypass this check with --no-verify."
)


class ExitCode(enum.IntEnum):
    """Process exit status of this script."""

    OK = 0
    BLOCKED = 1
    GIT_FAILED = 2


class BlockedPath(enum.StrEnum):
    """Why a staged path is refused on its name alone."""

    ENV_FILE = "an environment file (.env, .env.*) can hold real values; commit .env.example instead"
    DIRENV_FILE = "a direnv file (.envrc, .envrc.*) can export real values"
    SECRETS_DIRECTORY = "files under a secrets/ directory hold credentials"
    KEY_FILE = "a .pem or .key file is a key or certificate container"
    SSH_KEY = "an id_rsa* file is an SSH key"
    PERSONAL_SETTINGS = "personal agent settings stay local (they are gitignored)"


class SecretKind(enum.StrEnum):
    """A credential shape searched for in staged content."""

    AWS_ACCESS_KEY = "AWS access key"
    GITHUB_PAT = "GitHub token"
    GITHUB_FINE_GRAINED_PAT = "GitHub fine-grained token"
    ANTHROPIC_API_KEY = "Anthropic API key"
    OPENAI_PROJECT_KEY = "OpenAI project key"
    OPENROUTER_API_KEY = "OpenRouter API key"
    SLACK_CREDENTIAL = "Slack token"
    STRIPE_LIVE_KEY = "Stripe live secret key"
    PRIVATE_KEY = "private key"


# Every prefix must be followed by a token body, so a document (or this file)
# that merely names a prefix such as `ghp_` is not refused. Each minimum body
# length is at or below the length of the real tokens that issuer hands out.
# The PEM header covers every key type, including OPENSSH and ENCRYPTED keys.
SECRET_PATTERNS: Final[tuple[tuple[SecretKind, re.Pattern[str]], ...]] = (
    (SecretKind.AWS_ACCESS_KEY, re.compile(r"AKIA[0-9A-Z]{16}")),
    (SecretKind.GITHUB_PAT, re.compile(r"ghp_[A-Za-z0-9]{36}")),
    (SecretKind.GITHUB_FINE_GRAINED_PAT, re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    (SecretKind.ANTHROPIC_API_KEY, re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    (SecretKind.OPENAI_PROJECT_KEY, re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
    (SecretKind.OPENROUTER_API_KEY, re.compile(r"sk-or-[A-Za-z0-9_-]{20,}")),
    (SecretKind.SLACK_CREDENTIAL, re.compile(r"xox[abposr]-[A-Za-z0-9-]{10,}")),
    (SecretKind.STRIPE_LIVE_KEY, re.compile(r"sk_live_[A-Za-z0-9]{20,}")),
    (SecretKind.PRIVATE_KEY, re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")),
)


class GitError(Exception):
    """Git could not list or read the staged changes."""


@dataclass(frozen=True, slots=True)
class StagedEntry:
    """One added, modified, or type-changed path in the index."""

    path: str
    mode: str
    blob_id: str


@dataclass(frozen=True, slots=True)
class Finding:
    """One refused staged path and the rule that refused it."""

    path: str
    reason: str


def _run_git(args: Sequence[str], stdin: bytes | None = None) -> bytes:
    """Run git in the current directory and return its standard output.

    Raises:
        GitError: git could not be started or exited non-zero.
    """
    command = ["git", *args]
    try:
        completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell
            command,
            input=stdin,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        msg = f"could not run `{' '.join(command)}`: {error}"
        raise GitError(msg) from error
    if completed.returncode != 0:
        stderr = os.fsdecode(completed.stderr).strip()
        msg = f"`{' '.join(command)}` exited {completed.returncode}: {stderr}"
        raise GitError(msg)
    return completed.stdout


def staged_entries() -> list[StagedEntry]:
    """List the staged additions, modifications, and type changes.

    The listing ignores user configuration that would change its shape:
    `diff.relative` (paths relative to the current directory), colour, and
    rename or copy detection (two paths per entry).

    Returns:
        One entry per staged path that has content to commit, in index order.

    Raises:
        GitError: git could not list the index.
    """
    output = _run_git(
        [
            "diff",
            "--cached",
            "--raw",
            "-z",
            "--no-abbrev",
            "--no-renames",
            "--no-relative",
            "--no-color",
            f"--diff-filter={STAGED_STATUS_FILTER}",
        ],
    )
    fields = output.split(b"\0")
    entries = []
    for index in range(0, len(fields) - 1, RAW_FIELDS_PER_ENTRY):
        meta = fields[index].decode("ascii").split()
        if len(meta) != RAW_META_WORDS:
            msg = f"unexpected `git diff --raw` record: {fields[index]!r}"
            raise GitError(msg)
        _, new_mode, _, new_blob_id, _ = meta
        entries.append(
            StagedEntry(
                path=os.fsdecode(fields[index + 1]),
                mode=new_mode,
                blob_id=new_blob_id,
            ),
        )
    return entries


def _is_personal_settings(path: PurePosixPath) -> bool:
    return path.as_posix() in PERSONAL_SETTINGS_PATHS


def _is_under_secrets_directory(path: PurePosixPath) -> bool:
    return SECRETS_DIRECTORY in path.parts[:-1]


def _is_env_file(path: PurePosixPath) -> bool:
    return path.name == ENV_FILE_NAME or (
        path.name.startswith(f"{ENV_FILE_NAME}.") and path.name != ENV_EXAMPLE_NAME
    )


def _is_direnv_file(path: PurePosixPath) -> bool:
    return path.name == DIRENV_FILE_NAME or path.name.startswith(f"{DIRENV_FILE_NAME}.")


def _is_key_file(path: PurePosixPath) -> bool:
    return path.name.endswith(KEY_FILE_SUFFIXES)


def _is_ssh_key(path: PurePosixPath) -> bool:
    return path.name.startswith(SSH_KEY_PREFIX)


# Checked in order; the first rule that matches names the reason.
PATH_RULES: Final[tuple[tuple[BlockedPath, Callable[[PurePosixPath], bool]], ...]] = (
    (BlockedPath.PERSONAL_SETTINGS, _is_personal_settings),
    (BlockedPath.SECRETS_DIRECTORY, _is_under_secrets_directory),
    (BlockedPath.ENV_FILE, _is_env_file),
    (BlockedPath.DIRENV_FILE, _is_direnv_file),
    (BlockedPath.KEY_FILE, _is_key_file),
    (BlockedPath.SSH_KEY, _is_ssh_key),
)


def blocked_path_reason(path: str) -> BlockedPath | None:
    """Return why a repository-relative path must never be committed.

    Paths are compared case-insensitively: on the case-insensitive file
    systems macOS and Windows use by default, `.ENV` is the same file as
    `.env`.

    Args:
        path: A path relative to the repository root, `/`-separated.

    Returns:
        The rule that refuses the path, or None when the path is allowed.
    """
    lowered = PurePosixPath(path.lower())
    return next((reason for reason, matches in PATH_RULES if matches(lowered)), None)


def secret_kind(content: bytes) -> SecretKind | None:
    """Return the first credential shape found in a blob's content.

    Content that is not valid UTF-8 (an image, an archive) is not scanned:
    the patterns are textual, and a lossy decode would only add noise.

    Args:
        content: The raw bytes of one staged blob.

    Returns:
        The matching credential kind, or None when nothing matches.
    """
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    for kind, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return kind
    return None


def read_blobs(blob_ids: Sequence[str]) -> list[bytes]:
    """Read blobs by id through a single `git cat-file --batch` process.

    Args:
        blob_ids: Object ids of blobs in the index.

    Returns:
        The content of each blob, in the order requested.

    Raises:
        GitError: git failed, or answered with anything but the requested blob.
    """
    if not blob_ids:
        return []
    request = "".join(f"{blob_id}\n" for blob_id in blob_ids).encode("ascii")
    output = _run_git(["cat-file", "--batch"], stdin=request)
    contents = []
    offset = 0
    for blob_id in blob_ids:
        header_end = output.find(b"\n", offset)
        header = output[offset : header_end if header_end >= 0 else len(output)]
        words = header.decode("ascii", errors="replace").split()
        if (
            header_end < 0
            or len(words) != BATCH_HEADER_WORDS
            or words[0] != blob_id
            or words[1] != BLOB_TYPE
            or not words[2].isdigit()
        ):
            # The header is not echoed: a misaligned frame could be blob content.
            msg = f"`git cat-file --batch` did not return blob {blob_id}"
            raise GitError(msg)
        start = header_end + 1
        end = start + int(words[2])
        if output[end : end + 1] != FRAME_TERMINATOR:
            msg = f"`git cat-file --batch` returned a truncated blob {blob_id}"
            raise GitError(msg)
        contents.append(output[start:end])
        offset = end + 1
    return contents


def find_violations() -> list[Finding]:
    """Judge every staged change in the current repository.

    Returns:
        Every refused path, in index order; empty when the commit is safe.

    Raises:
        GitError: git could not list or read the staged changes.
    """
    entries = staged_entries()
    path_reasons = {entry.path: blocked_path_reason(entry.path) for entry in entries}
    to_read = [
        entry
        for entry in entries
        if path_reasons[entry.path] is None and entry.mode != GITLINK_MODE
    ]
    contents = dict(
        zip(
            (entry.path for entry in to_read),
            read_blobs([entry.blob_id for entry in to_read]),
            strict=True,
        ),
    )
    findings = []
    for entry in entries:
        if (path_reason := path_reasons[entry.path]) is not None:
            findings.append(Finding(entry.path, path_reason.value))
        elif entry.path in contents and (kind := secret_kind(contents[entry.path])):
            findings.append(
                Finding(entry.path, f"content matches the {kind.value} pattern"),
            )
    return findings


def main(argv: Sequence[str] | None = None) -> int:
    """Check the index and report every refused path on stderr.

    Args:
        argv: Command-line arguments; the script takes none besides --help.

    Returns:
        An `ExitCode` value.
    """
    parser = argparse.ArgumentParser(
        description="Refuse staged secret-shaped paths and credential-shaped content.",
    )
    parser.parse_args(argv)
    try:
        findings = find_violations()
    except GitError as error:
        print(f"check_staged: {error}", file=sys.stderr)
        return ExitCode.GIT_FAILED
    for finding in findings:
        print(
            f"check_staged: refused {finding.path}: {finding.reason}", file=sys.stderr
        )
    if findings:
        print(f"check_staged: {FIX_HINT}", file=sys.stderr)
        return ExitCode.BLOCKED
    return ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
