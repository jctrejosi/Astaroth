"""Logging estructurado (una línea JSON por registro) con request id de correlación.

No se registran payloads completos por defecto: los requests pueden contener
datos comerciales. Los campos disponibles siguen el contrato de observabilidad
del servicio (ruta, tipo de problema, dimensiones, estado, tiempos, versión del
motor y categoría de fallo).
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Request id de la petición en curso, si existe."""
    return request_id_var.get()


def set_request_id(value: str | None) -> Token[str | None]:
    """Fija el request id de la petición en curso y devuelve el token de reset."""
    return request_id_var.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    request_id_var.reset(token)


_RESERVED_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "asctime",
    "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Serializa cada registro como una línea JSON con campos estructurados."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except (TypeError, ValueError):  # pragma: no cover - salvaguarda extrema
            fallback = {key: payload[key] for key in ("timestamp", "level", "logger")}
            fallback["message"] = "registro no serializable"
            return json.dumps(fallback)


def configure_logging(level: str = "info") -> None:
    """Configura el logging raíz del proceso con el formatter JSON."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]

    # Los registros propios de uvicorn se unifican al logger raíz. El acceso
    # HTTP lo registra el middleware con campos estructurados, no uvicorn.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
