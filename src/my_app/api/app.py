"""The FastAPI application factory."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from my_app import __version__
from my_app.api.routers import health, todos
from my_app.composition import build_container
from my_app.core.errors import InvalidTodoError, TodoNotFoundError
from my_app.settings import Settings

APP_TITLE = "my-app"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application with its own services and storage.

    A factory rather than a module-level ``app`` so each test gets a fresh
    store, and so ``uvicorn --factory`` reads the environment only when the
    server starts.

    Args:
        settings: Configuration to build services from; read from the
            environment when omitted.

    Returns:
        The application, ready for uvicorn or ``TestClient``.
    """
    app = FastAPI(title=APP_TITLE, version=__version__)
    app.state.container = build_container(
        settings if settings is not None else Settings()
    )
    app.include_router(health.router)
    app.include_router(todos.router)
    _register_error_handlers(app)
    return app


def _register_error_handlers(app: FastAPI) -> None:
    """Map each domain error onto the status code clients rely on."""

    @app.exception_handler(TodoNotFoundError)
    async def _not_found(_: Request, error: TodoNotFoundError) -> JSONResponse:
        return _error_response(HTTPStatus.NOT_FOUND, error)

    @app.exception_handler(InvalidTodoError)
    async def _invalid(_: Request, error: InvalidTodoError) -> JSONResponse:
        return _error_response(HTTPStatus.UNPROCESSABLE_CONTENT, error)


def _error_response(status: HTTPStatus, error: Exception) -> JSONResponse:
    """Return FastAPI's usual ``{"detail": ...}`` body with the error's message."""
    return JSONResponse(status_code=status, content={"detail": str(error)})
