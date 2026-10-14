"""Handlers de error: todas las respuestas de error usan un único esquema JSON.

Los detalles de validación se limitan a ubicación, mensaje y tipo: nunca se
devuelve el cuerpo del request, dumps del modelo ni trazas internas.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..core.exceptions import HighsAPIError
from ..core.logging import get_logger

logger = get_logger(__name__)


def error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    """Esquema público único de error."""
    return {"error": {"code": code, "message": message, "details": details}}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_payload(code, message, details))


def _safe_validation_details(errors: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Ubicación, mensaje y tipo de cada error; sin ``input`` ni contexto."""
    details: list[dict[str, Any]] = []
    for error in errors:
        details.append(
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
        )
    return details


async def _highs_error_handler(request: Request, exc: HighsAPIError) -> JSONResponse:
    log = logger.warning if exc.code == "VALIDATION_ERROR" else logger.error
    log(
        "api_error",
        extra={
            "path": request.url.path,
            "error_code": exc.code,
            "http_status": exc.http_status,
            "error_message": exc.message,
        },
    )
    return error_response(exc.http_status, exc.code, exc.message, exc.details)


async def _fastapi_validation_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        "validation_error",
        extra={"path": request.url.path, "error_code": "VALIDATION_ERROR"},
    )
    return error_response(
        422,
        "VALIDATION_ERROR",
        "El request no cumple el contrato esperado.",
        _safe_validation_details(exc.errors()),
    )


async def _pydantic_validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
    logger.warning(
        "validation_error",
        extra={"path": request.url.path, "error_code": "VALIDATION_ERROR"},
    )
    return error_response(
        422,
        "VALIDATION_ERROR",
        "El request no cumple el contrato esperado.",
        _safe_validation_details(exc.errors()),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "unhandled_error",
        extra={"path": request.url.path, "error_type": type(exc).__name__},
    )
    return error_response(500, "INTERNAL_ERROR", "Fallo interno del servicio.")


def register_exception_handlers(app: FastAPI) -> None:
    """Registra los handlers propios, de FastAPI/Pydantic y de fallos inesperados."""
    app.add_exception_handler(HighsAPIError, _highs_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _fastapi_validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, _pydantic_validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
