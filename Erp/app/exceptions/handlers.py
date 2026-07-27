"""Global exception handlers → consistent JSON error envelope."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import AppError

log = logging.getLogger("erp")


def _envelope(code: str, message: str, details=None, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return _envelope(exc.code, exc.message, exc.details, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]) or str(e["loc"][0]),
             "message": e["msg"]}
            for e in exc.errors()
        ]
        return _envelope("VALIDATION_ERROR", "Request validation failed.",
                         {"fields": details}, 422)

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError):
        log.warning("Integrity error: %s", exc.orig)
        return _envelope("CONFLICT", "A record with these details already exists "
                                     "or a referenced record is missing.", None, 409)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        return _envelope("HTTP_ERROR", str(exc.detail), None, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):  # pragma: no cover
        log.exception("Unhandled error", exc_info=exc)
        return _envelope("INTERNAL_ERROR",
                         "Something went wrong on our side. Please try again.",
                         None, 500)
