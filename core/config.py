"""Utilidades de configuración mínimas (stdlib puro)."""

import os


def env(key: str, default: str | None = None, prefix: str = "ASTAROTH_") -> str | None:
    """Lee una variable de entorno con prefijo, p. ej. env('LOG_LEVEL')."""
    return os.getenv(prefix + key, default)
