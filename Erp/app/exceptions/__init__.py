"""Application exception hierarchy.

Every domain error the API can raise is a subclass of :class:`AppError`.
The global handlers in :mod:`app.exceptions.handlers` translate these into a
consistent JSON envelope::

    {"error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}
"""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthError(AppError):
    status_code = 401
    code = "UNAUTHENTICATED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE"


class InsufficientStockError(BusinessRuleError):
    code = "INSUFFICIENT_STOCK"


class RateLimitError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
