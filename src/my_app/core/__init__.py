"""Domain model, ports, and services, free of any framework or I/O library.

Nothing here may import fastapi, typer, uvicorn, sqlite3, or httpx: ruff's
TID251 rule and ``tests/core/test_imports.py`` both enforce it, so the same
services serve every entry point and every storage adapter.
"""
