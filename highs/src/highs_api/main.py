"""Aplicación FastAPI del motor `highs`: composición de middlewares, handlers y rutas."""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .api import capabilities, lp_routes, mip_routes, qp_routes
from .api.api_key_auth import APIKeyMiddleware
from .api.errors import register_exception_handlers
from .api.middleware import MaxBodySizeMiddleware, RequestLoggerMiddleware
from .config import settings
from .core.logging import configure_logging


def create_app() -> FastAPI:
    """Crea la aplicación: logging, middlewares, handlers de error y routers."""
    configure_logging(settings.log_level)
    app = FastAPI(
        title="highs",
        version=__version__,
        description=(
            "Motor de optimización LP/MIP/QP sobre HiGHS. Cada request es "
            "autocontenido: la API no conserva modelos entre llamadas."
        ),
    )
    # Autenticación por clave antes de procesar el cuerpo de la petición.
    app.add_middleware(APIKeyMiddleware)
    # El middleware de logging debe ser el más externo para abarcar todo el ciclo.
    app.add_middleware(MaxBodySizeMiddleware)
    app.add_middleware(RequestLoggerMiddleware)
    register_exception_handlers(app)

    app.include_router(capabilities.router)
    app.include_router(lp_routes.router)
    app.include_router(mip_routes.router)
    app.include_router(qp_routes.router)

    @app.get("/health", tags=["health"], summary="Liveness del proceso HTTP")
    def health() -> dict[str, str]:
        """Comprobación mínima: sin versiones, rutas internas ni configuración."""
        return {"status": "ok"}

    return app


app = create_app()
