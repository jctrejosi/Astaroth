"""Excepciones de aplicación, con código público y estado HTTP asociados.

Los estados de optimización (infactible, no acotado, límites) no son errores y
no se representan mediante excepciones: son parte normal de la respuesta.
"""

from __future__ import annotations

from typing import Any


class HighsAPIError(Exception):
    """Base de los errores controlados del servicio."""

    code: str = "INTERNAL_ERROR"
    http_status: int = 500
    default_message: str = "Fallo interno del servicio."

    def __init__(self, message: str | None = None, *, details: Any | None = None) -> None:
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class ModelValidationError(HighsAPIError):
    """Validación semántica propia del modelo u opciones (HTTP 422)."""

    code = "VALIDATION_ERROR"
    http_status = 422
    default_message = "El modelo enviado no es válido."


class SolverExecutionError(HighsAPIError):
    """El motor no pudo procesar el modelo (HTTP 500, categoría SOLVER_ERROR)."""

    code = "SOLVER_ERROR"
    http_status = 500
    default_message = "El motor de optimización no pudo procesar el modelo."


class InternalServiceError(HighsAPIError):
    """Fallo inesperado del servicio (HTTP 500)."""

    code = "INTERNAL_ERROR"
    http_status = 500


class RequestTooLargeError(HighsAPIError):
    """Cuerpo del request superior al límite configurado (HTTP 413)."""

    code = "REQUEST_TOO_LARGE"
    http_status = 413
    default_message = "El cuerpo del request supera el límite permitido."
