"""The core stays framework-free: it imports only the stdlib and itself.

Ruff's TID251 rule bans the same modules at lint time; this test backs it up
and is stricter, since it also rejects any third-party import (Pydantic
included) and any reach out of ``my_app.core`` into another layer. It walks
``core/`` recursively, so a subpackage added later is checked too.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

import my_app.core

CORE_PACKAGE = "my_app.core"
CORE_DIR = Path(my_app.core.__file__).parent
BANNED_MODULES = frozenset({"fastapi", "typer", "uvicorn", "sqlite3", "httpx"})
CORE_MODULE_PATHS = sorted(CORE_DIR.rglob("*.py"))


def _package_of(path: Path) -> str:
    """Return the package a core file's relative imports are resolved against."""
    subpackages = path.relative_to(CORE_DIR).parent.parts
    return ".".join([CORE_PACKAGE, *subpackages])


def _imported_modules(source: str, package: str = CORE_PACKAGE) -> set[str]:
    """Return every module a core file imports, relative imports resolved."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        match node:
            case ast.Import(names=aliases):
                modules.update(alias.name for alias in aliases)
            case ast.ImportFrom(module=module, level=0) if module is not None:
                modules.add(module)
            case ast.ImportFrom(module=module, level=level) if level > 0:
                parts = package.split(".")
                parent = parts[: len(parts) - level + 1]
                modules.add(".".join([*parent, module] if module else parent))
    return modules


def _is_allowed(module: str) -> bool:
    top_level = module.partition(".")[0]
    if top_level in BANNED_MODULES:
        return False
    is_core = module == CORE_PACKAGE or module.startswith(f"{CORE_PACKAGE}.")
    return is_core or top_level in sys.stdlib_module_names


def test_core_package_has_modules_to_check():
    assert CORE_DIR / "__init__.py" in CORE_MODULE_PATHS


@pytest.mark.parametrize(
    "path",
    CORE_MODULE_PATHS,
    ids=lambda path: path.relative_to(CORE_DIR).as_posix(),
)
def test_core_module_imports_only_stdlib_and_core(path):
    modules = _imported_modules(path.read_text(encoding="utf-8"), _package_of(path))

    disallowed = sorted(module for module in modules if not _is_allowed(module))

    assert disallowed == [], f"{path.name} imports {disallowed}"


@pytest.mark.parametrize(
    ("source", "module"),
    [
        pytest.param("import fastapi", "fastapi", id="fastapi"),
        pytest.param(
            "from typer.testing import CliRunner", "typer.testing", id="typer"
        ),
        pytest.param("import uvicorn", "uvicorn", id="uvicorn"),
        pytest.param("import sqlite3", "sqlite3", id="sqlite3"),
        pytest.param("import httpx", "httpx", id="httpx"),
        pytest.param("from pydantic import BaseModel", "pydantic", id="pydantic"),
        pytest.param("from .. import api", "my_app", id="relative-escape"),
        pytest.param("from ..adapters import memory", "my_app.adapters", id="adapters"),
    ],
)
def test_import_check_forbidden_import_is_rejected(source, module):
    modules = _imported_modules(source)

    assert module in modules
    assert not _is_allowed(module)


def test_import_check_subpackage_relative_escape_is_rejected():
    subpackage_file = CORE_DIR / "billing" / "invoices.py"

    modules = _imported_modules(
        "from ...adapters import sqlite", _package_of(subpackage_file)
    )

    assert modules == {"my_app.adapters"}
    assert not _is_allowed("my_app.adapters")


@pytest.mark.parametrize(
    ("source", "package"),
    [
        pytest.param("from datetime import datetime", CORE_PACKAGE, id="stdlib"),
        pytest.param(
            "from my_app.core.errors import AppError", CORE_PACKAGE, id="core-absolute"
        ),
        pytest.param("from .errors import AppError", CORE_PACKAGE, id="core-relative"),
        pytest.param(
            "from ..errors import AppError",
            f"{CORE_PACKAGE}.billing",
            id="subpackage-relative",
        ),
    ],
)
def test_import_check_allowed_import_is_accepted(source, package):
    assert all(_is_allowed(module) for module in _imported_modules(source, package))
