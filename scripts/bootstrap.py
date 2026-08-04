"""Rename this template into a new project by replacing its placeholders."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

OLD_DISTRIBUTION_NAME = "my-package"
OLD_MODULE_NAME = "my_package"
OLD_TEMPLATE_SLUG = "uv-template"
OLD_GITHUB_USER = "your-username"
OLD_AUTHOR_NAME = "Your Name"
OLD_AUTHOR_EMAIL = "you@example.com"
# The same idea is worded differently per file, so both spellings are replaced.
OLD_DESCRIPTIONS = (
    "A short description of the project.",
    "A short description of what this library does.",
)

# `uv lock`/`uv sync` refuse anything published after this cutoff, so a fresh
# project starts two weeks behind the index rather than at the template's date.
EXCLUDE_NEWER_LAG_DAYS = 14
EXCLUDE_NEWER_PATTERN = re.compile(r'exclude-newer = "[^"]*"')
LICENSE_YEAR_PATTERN = re.compile(r"(Copyright \(c\) )\d{4}")

CHANGELOG_SKELETON = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
"""

# Template-only scaffolding, removed from the new project unless kept.
BOOTSTRAP_FILES = (
    "TEMPLATE.md",
    "scripts/bootstrap.py",
    "tests/test_bootstrap.py",
)

EXCLUDED_FILE_NAMES = {"uv.lock"}
# Only used for the non-git fallback walk (e.g. after ``.git`` was removed):
# generated/untracked directories that must never be rewritten.
EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    "site",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "htmlcov",
    ".tox",
    "node_modules",
}

_MODULE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _normalize_module_name(package_name: str) -> str:
    """Return the snake_case module name derived from a distribution name."""
    module_name = package_name.replace("-", "_")
    if not _MODULE_NAME_PATTERN.fullmatch(module_name):
        msg = (
            f"Invalid package name {package_name!r}: must become a valid Python "
            "identifier once hyphens are replaced with underscores."
        )
        raise SystemExit(msg)
    return module_name


def _git_tracked_files(repo_root: Path) -> list[Path] | None:
    """Return absolute paths of git-tracked files under repo_root.

    Returns:
        The tracked files (excluding EXCLUDED_FILE_NAMES), or None when
        repo_root is not a git repository or git is unavailable.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "-C", str(repo_root), "ls-files", "-z"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    files = []
    for relative_path in result.stdout.split("\0"):
        if not relative_path or Path(relative_path).name in EXCLUDED_FILE_NAMES:
            continue
        path = repo_root / relative_path
        if path.is_file():
            files.append(path)
    return files


def _walk_project_files(repo_root: Path) -> list[Path]:
    """Return every file under repo_root, skipping excluded dirs and files."""
    files = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in EXCLUDED_FILE_NAMES:
            continue
        if EXCLUDED_DIR_NAMES & set(path.relative_to(repo_root).parts):
            continue
        files.append(path)
    return files


def _iter_project_files(repo_root: Path) -> list[Path]:
    """Return the files to rewrite.

    Prefers git-tracked files so generated/untracked trees (``.venv``,
    caches, build output) are never read or rewritten. Falls back to a
    filtered filesystem walk when repo_root is not a git repository, e.g.
    after the template's ``.git`` directory has been removed.
    """
    tracked = _git_tracked_files(repo_root)
    if tracked is not None:
        return tracked
    return _walk_project_files(repo_root)


def _replace_placeholders_in_file(path: Path, replacements: dict[str, str]) -> bool:
    """Replace every placeholder occurrence in a single file.

    Returns:
        True if the file's contents changed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False

    new_text = text
    for old, new in replacements.items():
        new_text = new_text.replace(old, new)

    if new_text == text:
        return False

    path.write_text(new_text, encoding="utf-8")
    return True


def _rename_source_directory(repo_root: Path, new_module_name: str) -> None:
    """Rename src/my_package to src/<new_module_name> in place."""
    old_dir = repo_root / "src" / OLD_MODULE_NAME
    new_dir = repo_root / "src" / new_module_name
    if old_dir == new_dir:
        return
    if not old_dir.is_dir():
        msg = f"Expected source directory not found: {old_dir}"
        raise SystemExit(msg)
    shutil.move(str(old_dir), str(new_dir))


def _rewrite_exclude_newer(repo_root: Path, today: dt.date) -> None:
    """Move the supply-chain cutoff to two weeks before the run date."""
    pyproject = repo_root / "pyproject.toml"
    if not pyproject.is_file():
        return
    cutoff = today - dt.timedelta(days=EXCLUDE_NEWER_LAG_DAYS)
    text = pyproject.read_text(encoding="utf-8")
    new_text = EXCLUDE_NEWER_PATTERN.sub(
        f'exclude-newer = "{cutoff.isoformat()}T00:00:00Z"', text
    )
    if new_text != text:
        pyproject.write_text(new_text, encoding="utf-8")


def _rewrite_license_year(repo_root: Path, today: dt.date) -> None:
    """Set the LICENSE copyright year to the year of the run."""
    license_file = repo_root / "LICENSE"
    if not license_file.is_file():
        return
    text = license_file.read_text(encoding="utf-8")
    new_text = LICENSE_YEAR_PATTERN.sub(rf"\g<1>{today.year}", text)
    if new_text != text:
        license_file.write_text(new_text, encoding="utf-8")


def _reset_changelog(repo_root: Path) -> None:
    """Replace the template's changelog with an empty skeleton."""
    changelog = repo_root / "CHANGELOG.md"
    if not changelog.is_file():
        return
    changelog.write_text(CHANGELOG_SKELETON, encoding="utf-8")


def _delete_bootstrap_files(repo_root: Path) -> None:
    """Remove the template-only scaffolding from the new project."""
    for relative_path in BOOTSTRAP_FILES:
        (repo_root / relative_path).unlink(missing_ok=True)


def bootstrap(  # noqa: PLR0913
    repo_root: Path,
    package_name: str,
    author: str | None,
    email: str | None,
    github_user: str,
    description: str | None = None,
    *,
    keep_bootstrap: bool = False,
) -> str:
    """Rename the package and replace template placeholders in-place.

    Returns:
        The normalized module name the source directory was renamed to.
    """
    module_name = _normalize_module_name(package_name)
    today = dt.datetime.now(tz=dt.UTC).date()

    replacements = {
        OLD_MODULE_NAME: module_name,
        OLD_DISTRIBUTION_NAME: package_name,
        OLD_TEMPLATE_SLUG: package_name,
        OLD_GITHUB_USER: github_user,
    }
    if author:
        replacements[OLD_AUTHOR_NAME] = author
    if email:
        replacements[OLD_AUTHOR_EMAIL] = email
    if description:
        for old_description in OLD_DESCRIPTIONS:
            replacements[old_description] = description

    for path in _iter_project_files(repo_root):
        _replace_placeholders_in_file(path, replacements)

    _rewrite_exclude_newer(repo_root, today)
    _rewrite_license_year(repo_root, today)
    _reset_changelog(repo_root)
    _rename_source_directory(repo_root, module_name)
    if not keep_bootstrap:
        _delete_bootstrap_files(repo_root)
    return module_name


def _run_uv_lock(repo_root: Path) -> None:
    """Regenerate uv.lock, warning instead of aborting when it fails.

    CI runs ``uv sync --locked`` everywhere, so a lock still naming the
    template would fail the new project's very first run.
    """
    try:
        result = subprocess.run(
            ["uv", "lock"],  # noqa: S607
            cwd=repo_root,
            check=False,
        )
    except OSError as error:
        print(f"warning: could not run `uv lock` ({error}).", file=sys.stderr)
        return
    if result.returncode != 0:
        print(
            "warning: `uv lock` failed — run it manually before the first commit.",
            file=sys.stderr,
        )


def main(argv: list[str]) -> int:
    """Parse arguments and bootstrap the template in place."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="New package name, e.g. 'my-cool-lib'")
    parser.add_argument("--author", default=None, help="Author name")
    parser.add_argument("--email", default=None, help="Author email")
    parser.add_argument(
        "--github-user",
        required=True,
        help="GitHub username or org (required: it is baked into project URLs)",
    )
    parser.add_argument(
        "--description", default=None, help="One-line description of the project"
    )
    parser.add_argument(
        "--keep-bootstrap",
        action="store_true",
        help="Keep TEMPLATE.md and the bootstrap script instead of deleting them",
    )
    args = parser.parse_args(argv)

    module_name = bootstrap(
        REPO_ROOT,
        args.name,
        args.author,
        args.email,
        args.github_user,
        args.description,
        keep_bootstrap=args.keep_bootstrap,
    )
    _run_uv_lock(REPO_ROOT)

    print(f"Bootstrapped {args.name!r} (module: {module_name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
