"""Middlewares ASGI: request id de correlación, logging y límite de tamaño de request."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from ..config import settings
from ..core.exceptions import RequestTooLargeError
from ..core.logging import get_logger, reset_request_id, set_request_id
from .errors import error_payload

logger = get_logger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

_MAX_REQUEST_ID_LENGTH = 64


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", ()):
        if key == name:
            return value.decode("latin-1")
    return None


def _sanitize_request_id(raw: str | None) -> str:
    if (
        raw
        and 1 <= len(raw) <= _MAX_REQUEST_ID_LENGTH
        and all(character.isalnum() or character in "-_." for character in raw)
    ):
        return raw
    return uuid.uuid4().hex


class RequestLoggerMiddleware:
    """Fija un request id de correlación y registra cada petición HTTP.

    No registra query strings, cabeceras ni el cuerpo: solo método, ruta,
    estado y duración.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = _sanitize_request_id(_header(scope, b"x-request-id"))
        token = set_request_id(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
            logger.info(
                "http_request",
                extra={
                    "method": scope.get("method"),
                    "path": scope.get("path"),
                    "http_status": status_code,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)


class MaxBodySizeMiddleware:
    """Rechaza con HTTP 413 los cuerpos que superan el límite configurado.

    Se comprueba primero ``Content-Length`` para rechazar de forma temprana;
    cuando no hay longitud declarada, se cuenta el cuerpo real mientras se lee.
    El límite se consulta en cada request para respetar la configuración vigente.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = settings.max_request_bytes
        declared = _header(scope, b"content-length")
        if declared is not None:
            try:
                declared_length: int | None = int(declared)
            except ValueError:
                declared_length = None
            if declared_length is not None and declared_length > limit:
                await _send_too_large(send)
                return

        consumed = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > limit:
                    raise RequestTooLargeError()
            return message

        async def send_wrapper(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except RequestTooLargeError:
            if response_started:
                raise
            await _send_too_large(send)


async def _send_too_large(send: Send) -> None:
    exc = RequestTooLargeError()
    body = json.dumps(error_payload(exc.code, exc.message)).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": exc.http_status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
