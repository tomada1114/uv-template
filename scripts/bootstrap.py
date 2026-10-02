"""Rename this template into a new project by replacing its placeholders."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import keyword
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

OLD_DISTRIBUTION_NAME = "my-package"
OLD_MODULE_NAME = "my_package"
OLD_REPOSITORY_NAME = "uv-template"
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
ENV_EXAMPLE_SUFFIXES = (".example", ".sample", ".template")
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
    "secrets",
}

_DISTRIBUTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_GITHUB_USER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_REPOSITORY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_EMAIL_PATTERN = re.compile(r"^[^@\s<>]+@[^@\s<>]+$")
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")

_TOML_DESCRIPTION_PATTERN = re.compile(r'(?m)^(?P<prefix>\s*description\s*=\s*)"[^"]*"')
_TOML_AUTHOR_PATTERN = re.compile(
    r'(?P<prefix>\bname\s*=\s*)"[^"]*"(?P<suffix>\s*,\s*email\s*=)'
)
_TOML_EMAIL_PATTERN = re.compile(r'(?P<prefix>\bemail\s*=\s*)"[^"]*"')
_MKDOCS_DESCRIPTION_PATTERN = re.compile(
    r'(?m)^(?P<prefix>\s*site_description:\s*)"[^"]*"'
)


def _normalize_module_name(package_name: str) -> str:
    """Return the snake_case module name derived from a distribution name."""
    if not _DISTRIBUTION_NAME_PATTERN.fullmatch(package_name):
        msg = (
            f"Invalid package name {package_name!r}: use letters, numbers, "
            "periods, hyphens, or underscores, starting with a letter or number."
        )
        raise SystemExit(msg)

    module_name = re.sub(r"[-.]+", "_", package_name).lower()
    if not module_name.isidentifier() or keyword.iskeyword(module_name):
        msg = (
            f"Invalid package name {package_name!r}: must become a valid Python "
            "module name once hyphens and periods are replaced with underscores."
        )
        raise SystemExit(msg)
    return module_name


def _validate_single_line(value: str | None, label: str) -> None:
    """Reject values that would create malformed generated files."""
    if value is not None and _CONTROL_CHARACTER_PATTERN.search(value):
        msg = f"Invalid {label}: it must be a single line without control characters."
        raise SystemExit(msg)


def _validate_inputs(  # noqa: PLR0913
    package_name: str,
    author: str | None,
    email: str | None,
    github_user: str,
    github_repository: str | None,
    description: str | None,
) -> str:
    """Validate bootstrap inputs and return the normalized module name."""
    module_name = _normalize_module_name(package_name)
    if not _GITHUB_USER_PATTERN.fullmatch(github_user):
        msg = f"Invalid GitHub user or organization {github_user!r}."
        raise SystemExit(msg)

    repository = package_name if github_repository is None else github_repository
    if not _REPOSITORY_NAME_PATTERN.fullmatch(repository):
        msg = f"Invalid GitHub repository name {repository!r}."
        raise SystemExit(msg)

    _validate_single_line(author, "author")
    _validate_single_line(email, "email")
    _validate_single_line(description, "description")
    if email is not None and not _EMAIL_PATTERN.fullmatch(email):
        msg = f"Invalid email address {email!r}."
        raise SystemExit(msg)
    return module_name


def _is_protected_path(path: Path) -> bool:
    """Return whether a path may contain credentials rather than placeholders."""
    name = path.name
    if name == ".env" or (
        name.startswith(".env.") and not name.endswith(ENV_EXAMPLE_SUFFIXES)
    ):
        return True
    return "secrets" in path.parts


def _git_tracked_files(repo_root: Path) -> list[Path] | None:
    """Return absolute paths of git-tracked files under repo_root.

    Returns:
        The tracked files (excluding protected files), or None when repo_root
        is not a Git repository and a filesystem walk is therefore required.
        A Git failure inside a repository raises instead of widening the write
        scope to untracked files.
    """
    try:
        top_level = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
            check=False,
            capture_output=True,
            cwd=repo_root,
            text=True,
        )
    except OSError as error:
        if (repo_root / ".git").exists():
            msg = f"Git is unavailable while inspecting {repo_root}: {error}"
            raise SystemExit(msg) from error
        return None

    if top_level.returncode != 0:
        if not (repo_root / ".git").exists():
            return None
        msg = f"Could not identify the Git root for {repo_root}: {top_level.stderr.strip()}"
        raise SystemExit(msg)
    git_root = Path(top_level.stdout.strip()).resolve()
    if git_root != repo_root:
        msg = (
            f"Bootstrap must run at the Git root ({repo_root}); "
            f"Git found an ancestor root at {git_root}."
        )
        raise SystemExit(msg)

    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],  # noqa: S607
            check=False,
            capture_output=True,
            cwd=repo_root,
            text=True,
        )
    except OSError as error:
        if (repo_root / ".git").exists():
            msg = f"Git is unavailable while inspecting {repo_root}: {error}"
            raise SystemExit(msg) from error
        return None

    if result.returncode != 0:
        if not (repo_root / ".git").exists():
            return None
        msg = f"Could not list tracked files in {repo_root}: {result.stderr.strip()}"
        raise SystemExit(msg)

    files = []
    for relative_path in result.stdout.split("\0"):
        if not relative_path or Path(relative_path).name in EXCLUDED_FILE_NAMES:
            continue
        path = repo_root / relative_path
        if path.is_file() and not path.is_symlink() and not _is_protected_path(path):
            files.append(path)
    return files


def _walk_project_files(repo_root: Path) -> list[Path]:
    """Return every file under repo_root, skipping excluded dirs and files."""
    files = []
    for path in repo_root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name in EXCLUDED_FILE_NAMES:
            continue
        if EXCLUDED_DIR_NAMES & set(path.relative_to(repo_root).parts):
            continue
        if _is_protected_path(path):
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


def _replace_placeholders_in_file(
    path: Path,
    replacements: dict[str, str],
    *,
    python_literals: bool = False,
) -> bool:
    """Replace every placeholder occurrence in a single file.

    Returns:
        True if the file's contents changed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False

    if python_literals:
        literal_values = "|".join(
            re.escape(old) for old in sorted(replacements, key=len, reverse=True)
        )
        literal_pattern = re.compile(
            rf"(?P<quote>['\"])(?P<value>{literal_values})(?P=quote)"
        )
        new_text = literal_pattern.sub(
            lambda match: (
                _quoted_string(replacements[match.group("value")])
                if match.group("quote") == '"'
                else repr(replacements[match.group("value")])
            ),
            text,
        )
    else:
        placeholder_pattern = re.compile(
            "|".join(
                re.escape(old) for old in sorted(replacements, key=len, reverse=True)
            )
        )
        new_text = placeholder_pattern.sub(
            lambda match: replacements[match.group(0)],
            text,
        )

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
    if new_dir.exists() or new_dir.is_symlink():
        msg = f"Destination source directory already exists: {new_dir}"
        raise SystemExit(msg)
    shutil.move(str(old_dir), str(new_dir))


def _quoted_string(value: str) -> str:
    """Encode a value as a double-quoted string literal."""
    return json.dumps(value, ensure_ascii=False)


def _rewrite_project_metadata(
    repo_root: Path,
    author: str | None,
    email: str | None,
    description: str | None,
) -> None:
    """Write user-provided metadata with syntax-safe TOML and YAML quoting."""
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        text = pyproject.read_text(encoding="utf-8")
        if description:
            text = _TOML_DESCRIPTION_PATTERN.sub(
                lambda match: f"{match.group('prefix')}{_quoted_string(description)}",
                text,
                count=1,
            )
        if author:
            text = _TOML_AUTHOR_PATTERN.sub(
                lambda match: (
                    f"{match.group('prefix')}{_quoted_string(author)}"
                    f"{match.group('suffix')}"
                ),
                text,
                count=1,
            )
        if email:
            text = _TOML_EMAIL_PATTERN.sub(
                lambda match: f"{match.group('prefix')}{_quoted_string(email)}",
                text,
                count=1,
            )
        pyproject.write_text(text, encoding="utf-8")

    mkdocs = repo_root / "mkdocs.yml"
    if description and mkdocs.is_file():
        text = mkdocs.read_text(encoding="utf-8")
        text = _MKDOCS_DESCRIPTION_PATTERN.sub(
            lambda match: f"{match.group('prefix')}{_quoted_string(description)}",
            text,
            count=1,
        )
        mkdocs.write_text(text, encoding="utf-8")


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
    github_repository: str | None = None,
    keep_bootstrap: bool = False,
) -> str:
    """Rename the package and replace template placeholders in-place.

    Returns:
        The normalized module name the source directory was renamed to.
    """
    module_name = _validate_inputs(
        package_name,
        author,
        email,
        github_user,
        github_repository,
        description,
    )
    repository_name = package_name if github_repository is None else github_repository
    repo_root = repo_root.resolve()
    old_dir = repo_root / "src" / OLD_MODULE_NAME
    new_dir = repo_root / "src" / module_name
    if not old_dir.is_dir():
        msg = f"Expected source directory not found: {old_dir}"
        raise SystemExit(msg)
    if old_dir != new_dir and (new_dir.exists() or new_dir.is_symlink()):
        msg = f"Destination source directory already exists: {new_dir}"
        raise SystemExit(msg)

    today = dt.datetime.now(tz=dt.UTC).date()

    replacements = {
        OLD_MODULE_NAME: module_name,
        OLD_DISTRIBUTION_NAME: package_name,
        OLD_REPOSITORY_NAME: repository_name,
        OLD_GITHUB_USER: github_user,
    }

    project_files = _iter_project_files(repo_root)
    pyproject = repo_root / "pyproject.toml"
    mkdocs = repo_root / "mkdocs.yml"
    for path in project_files:
        _replace_placeholders_in_file(path, replacements)
        file_replacements: dict[str, str] = {}
        if path != pyproject:
            if author:
                file_replacements[OLD_AUTHOR_NAME] = author
            if email:
                file_replacements[OLD_AUTHOR_EMAIL] = email
        if path not in (pyproject, mkdocs) and description:
            for old_description in OLD_DESCRIPTIONS:
                file_replacements[old_description] = description
        if file_replacements:
            _replace_placeholders_in_file(
                path,
                file_replacements,
                python_literals=path.suffix == ".py",
            )

    _rewrite_exclude_newer(repo_root, today)
    _rewrite_project_metadata(repo_root, author, email, description)
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
        "--github-repository",
        default=None,
        help="GitHub repository name (defaults to the package name)",
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
        github_repository=args.github_repository,
        keep_bootstrap=args.keep_bootstrap,
    )
    _run_uv_lock(REPO_ROOT)

    print(f"Bootstrapped {args.name!r} (module: {module_name}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
