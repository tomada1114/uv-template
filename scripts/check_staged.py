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

During a merge, a staged entry whose blob (and mode) is identical to the one at
the same path in a commit being merged in is not judged again: that content was
judged when it entered the other side's history. Re-judging it would refuse
every later merge of that branch once anything matching had landed on it, and
the only way out would be to drop the other side's file. Conflict resolutions
and any other content new to both sides are still judged.

The script is stdlib-only and runs on Python 3.10+, the oldest interpreter
pre-commit itself supports, because pre-commit runs it (`language: python`)
with its own interpreter rather than the project's environment.

Usage:
    python scripts/check_staged.py

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
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Sequence

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

CLAUDE_DIRECTORY: Final = ".claude"
CLAUDE_LOCAL_SETTINGS_NAME: Final = "settings.local.json"
CODEX_LOCAL_RULES_PATH: Final = ".codex/rules/local.rules"
MERGE_HEAD_REF: Final = "MERGE_HEAD"
GITHEAD_ENV_PREFIX: Final = "GITHEAD_"
OBJECT_ID: Final = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# Shared by every listing so user configuration cannot change its shape:
# `diff.relative` (paths relative to the current directory), colour, and
# rename or copy detection (two paths per entry).
RAW_DIFF_ARGS: Final = (
    "diff",
    "--cached",
    "--raw",
    "-z",
    "--no-abbrev",
    "--no-renames",
    "--no-relative",
    "--no-color",
)

FIX_HINT: Final = (
    "Remove the secret from the file and `git add` it again, or take the path "
    "out of the index with `git rm --cached <path>` and list it in .gitignore. "
    "Never bypass this check with --no-verify."
)
MERGE_FIX_HINT: Final = (
    "A merge is in progress: remove the secret from each refused file and "
    "`git add` it again. Do not `git rm --cached` or `git restore --staged` a "
    "path here -- that would also drop the other side's change to it. "
    "Never bypass this check with --no-verify."
)


class ExitCode(enum.IntEnum):
    """Process exit status of this script."""

    OK = 0
    BLOCKED = 1
    GIT_FAILED = 2


# `str, Enum` rather than StrEnum, which needs 3.11 (see the module docstring).
class BlockedPath(str, enum.Enum):
    """Why a staged path is refused on its name alone."""

    ENV_FILE = "an environment file (.env, .env.*) can hold real values; commit .env.example instead"
    DIRENV_FILE = "a direnv file (.envrc, .envrc.*) can export real values"
    SECRETS_DIRECTORY = "files under a secrets/ directory hold credentials"
    KEY_FILE = "a .pem or .key file is a key or certificate container"
    SSH_KEY = "an id_rsa* file is an SSH key"
    PERSONAL_SETTINGS = "personal agent settings stay local (they are gitignored)"


class SecretKind(str, enum.Enum):
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
# A token prefix must also start a word: without that left boundary, prose such
# as "risk-or-reward-..." or "desk-proj-overview-..." would read as a key.
# A Slack token body starts with a digit (a workspace or version number), which
# keeps a word like "xoxo-gossip-..." from matching even at a word start.
WORD_START: Final = r"(?<![A-Za-z0-9_-])"
# The PEM header covers the PEM private-key types (RSA, EC, DSA, OPENSSH,
# ENCRYPTED, and plain PKCS#8); an armored PGP key ("PRIVATE KEY BLOCK") is
# not PEM and is not matched.
SECRET_PATTERNS: Final[tuple[tuple[SecretKind, re.Pattern[str]], ...]] = (
    (SecretKind.AWS_ACCESS_KEY, re.compile(r"AKIA[0-9A-Z]{16}")),
    (SecretKind.GITHUB_PAT, re.compile(rf"{WORD_START}ghp_[A-Za-z0-9]{{36}}")),
    (
        SecretKind.GITHUB_FINE_GRAINED_PAT,
        re.compile(rf"{WORD_START}github_pat_[A-Za-z0-9_]{{22,}}"),
    ),
    (
        SecretKind.ANTHROPIC_API_KEY,
        re.compile(rf"{WORD_START}sk-ant-[A-Za-z0-9_-]{{20,}}"),
    ),
    (
        SecretKind.OPENAI_PROJECT_KEY,
        re.compile(rf"{WORD_START}sk-proj-[A-Za-z0-9_-]{{20,}}"),
    ),
    (
        SecretKind.OPENROUTER_API_KEY,
        re.compile(rf"{WORD_START}sk-or-[A-Za-z0-9_-]{{20,}}"),
    ),
    (
        SecretKind.SLACK_CREDENTIAL,
        re.compile(rf"{WORD_START}xox[abposr]-[0-9][A-Za-z0-9-]{{9,}}"),
    ),
    (
        SecretKind.STRIPE_LIVE_KEY,
        re.compile(rf"{WORD_START}sk_live_[A-Za-z0-9]{{20,}}"),
    ),
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


def _raw_diff(*args: str) -> list[StagedEntry]:
    """Run `git diff --cached --raw` with `args` and parse its records.

    Raises:
        GitError: git failed or printed a record of an unexpected shape.
    """
    fields = _run_git([*RAW_DIFF_ARGS, *args]).split(b"\0")
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


def staged_entries() -> list[StagedEntry]:
    """List the staged additions, modifications, and type changes.

    Returns:
        One entry per staged path that has content to commit, in index order.

    Raises:
        GitError: git could not list the index.
    """
    return _raw_diff(f"--diff-filter={STAGED_STATUS_FILTER}")


def merge_heads() -> list[str]:
    """Return the commits being merged in, or an empty list outside a merge.

    Two sources, because git exposes the merge differently per hook. A clean
    `git merge` runs pre-merge-commit before it writes MERGE_HEAD, but exports
    a `GITHEAD_<commit id>` variable for each head it merges; the `git commit`
    that concludes a conflicted merge has MERGE_HEAD on disk instead.

    Raises:
        GitError: git could not locate the repository's MERGE_HEAD file.
    """
    from_environment = [
        name.removeprefix(GITHEAD_ENV_PREFIX)
        for name in os.environ
        if name.startswith(GITHEAD_ENV_PREFIX)
        and OBJECT_ID.fullmatch(name.removeprefix(GITHEAD_ENV_PREFIX))
    ]
    merge_head = Path(
        os.fsdecode(_run_git(["rev-parse", "--git-path", MERGE_HEAD_REF])).strip(),
    )
    try:
        from_file = merge_head.read_text(encoding="ascii").split()
    except FileNotFoundError:
        from_file = []
    return list(dict.fromkeys([*from_file, *from_environment]))


def paths_identical_in(commit: str, paths: Collection[str]) -> set[str]:
    """Return the paths whose staged blob and mode equal those in `commit`.

    Raises:
        GitError: git could not compare the index with `commit`.
    """
    differing = {entry.path for entry in _raw_diff(commit)}
    return {path for path in paths if path not in differing}


def _is_personal_settings(path: PurePosixPath) -> bool:
    # .claude/settings.local.json is gitignored at any depth; the Codex rules
    # file only at the root.
    is_claude_local = path.parts[-2:] == (CLAUDE_DIRECTORY, CLAUDE_LOCAL_SETTINGS_NAME)
    return is_claude_local or path.as_posix() == CODEX_LOCAL_RULES_PATH


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


def find_violations(merge_commits: Sequence[str] = ()) -> list[Finding]:
    """Judge every staged change in the current repository.

    Args:
        merge_commits: The commits being merged in (`merge_heads()`); a staged
            entry identical to the same path in one of them is not judged.

    Returns:
        Every refused path, in index order; empty when the commit is safe.

    Raises:
        GitError: git could not list or read the staged changes.
    """
    entries = staged_entries()
    inherited: set[str] = set()
    for commit in merge_commits:
        inherited |= paths_identical_in(commit, {entry.path for entry in entries})
    entries = [entry for entry in entries if entry.path not in inherited]
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
        merge_commits = merge_heads()
        findings = find_violations(merge_commits)
    except GitError as error:
        print(f"check_staged: {error}", file=sys.stderr)
        return ExitCode.GIT_FAILED
    for finding in findings:
        print(
            f"check_staged: refused {finding.path}: {finding.reason}", file=sys.stderr
        )
    if findings:
        hint = MERGE_FIX_HINT if merge_commits else FIX_HINT
        print(f"check_staged: {hint}", file=sys.stderr)
        return ExitCode.BLOCKED
    return ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
