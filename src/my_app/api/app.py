"""The FastAPI application factory and its domain-error mapping."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from my_app import __version__
from my_app.api.routers import health, todos
from my_app.api.schemas import ErrorResponse
from my_app.composition import Container, build_container
from my_app.core.errors import AppError, InvalidTodoError, TodoNotFoundError
from my_app.settings import Settings

APP_TITLE = "my-app"


def create_app(
    settings: Settings | None = None, *, container: Container | None = None
) -> FastAPI:
    """Build an application with its own services and storage.

    A factory rather than a module-level ``app`` so each test gets a fresh
    store, and so ``uvicorn --factory`` reads the environment only when the
    server starts.

    Args:
        settings: Configuration to build services from; read from the
            environment when omitted. Ignored when ``container`` is given.
        container: Services already built by the composition root. Tests pass
            one built with a fixed clock; production code leaves it out.

    Returns:
        The application, ready for uvicorn or ``TestClient``.
    """
    app = FastAPI(title=APP_TITLE, version=__version__)
    if container is None:
        container = build_container(settings if settings is not None else Settings())
    app.state.container = container
    app.include_router(health.router)
    app.include_router(todos.router)
    # The decorator form, unlike add_exception_handler, type-checks a handler
    # that takes AppError rather than any Exception.
    app.exception_handler(AppError)(_handle_app_error)
    return app


def _status_for(error: AppError) -> HTTPStatus:
    """Choose the HTTP status a domain error becomes.

    The one place the mapping lives, as ``cli.errors`` is for exit codes. Any
    ``AppError`` without a case here is still the client's problem, not the
    server's, so a new subclass is a 400 until it gets its own case — never
    an unhandled 500.

    Args:
        error: The domain error a service raised.

    Returns:
        The status to answer with.
    """
    match error:
        case TodoNotFoundError():
            return HTTPStatus.NOT_FOUND
        case InvalidTodoError():
            return HTTPStatus.UNPROCESSABLE_CONTENT
        case _:
            return HTTPStatus.BAD_REQUEST


async def _handle_app_error(_: Request, error: AppError) -> JSONResponse:
    """Answer a domain error with its status and an ``ErrorResponse`` body."""
    body = ErrorResponse(detail=str(error))
    return JSONResponse(status_code=_status_for(error), content=body.model_dump())
