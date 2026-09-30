"""Error handling: friendly HTML pages for the website, standard JSON for the API."""

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.templates import templates

ERROR_PAGES = {
    404: ("Page not found", "This listing may have been removed, or the link is incorrect."),
    422: ("Invalid search parameters", "Some filter values could not be understood."),
}
DEFAULT_ERROR = ("Something went wrong", "Please try again in a moment.")


def _wants_json(request: Request) -> bool:
    return request.url.path.startswith(("/api", "/docs", "/openapi.json", "/static"))


def _render_error(request: Request, status_code: int) -> Response:
    heading, message = ERROR_PAGES.get(status_code, DEFAULT_ERROR)
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": status_code, "heading": heading, "message": message},
        status_code=status_code,
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if _wants_json(request):
            return await http_exception_handler(request, exc)
        return _render_error(request, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
        if _wants_json(request):
            return await request_validation_exception_handler(request, exc)
        # e.g. /listings/abc is simply a page that does not exist
        status_code = 404 if request.url.path.startswith("/listings/") else 422
        return _render_error(request, status_code)
