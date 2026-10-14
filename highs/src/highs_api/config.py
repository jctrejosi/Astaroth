"""Configuración del servicio, cargada de variables de entorno con prefijo `HIGHS_`."""

from __future__ import annotations

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración efectiva del proceso.

    Las relaciones entre límites se validan al construir la instancia: una
    configuración inválida impide arrancar el servicio en vez de dejarlo en un
    estado parcialmente configurado.
    """

    model_config = SettingsConfigDict(
        env_prefix="HIGHS_",
        env_file=".env",
        extra="ignore",
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    output_flag: bool = False

    default_time_limit: float = 30.0
    default_threads: int = 0
    max_threads: int = 8

    max_variables: int = 100_000
    max_constraints: int = 100_000
    max_matrix_elements: int = 2_000_000
    max_qp_variables: int = 500
    max_request_bytes: int = 20 * 1024 * 1024
    max_time_limit_seconds: float = 600.0

    @model_validator(mode="after")
    def _validate_relations(self) -> Settings:
        if self.max_threads < 1:
            raise ValueError("max_threads debe ser al menos 1")
        if self.default_threads < 0 or self.default_threads > self.max_threads:
            raise ValueError("default_threads debe estar entre 0 y max_threads")
        if self.default_time_limit < 0:
            raise ValueError("default_time_limit no puede ser negativo")
        if self.default_time_limit > self.max_time_limit_seconds:
            raise ValueError("default_time_limit no puede superar max_time_limit_seconds")
        if self.max_time_limit_seconds <= 0:
            raise ValueError("max_time_limit_seconds debe ser mayor que cero")
        for name in ("max_variables", "max_constraints", "max_matrix_elements", "max_qp_variables"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} debe ser mayor que cero")
        if self.max_qp_variables > self.max_variables:
            raise ValueError("max_qp_variables no puede superar max_variables")
        if self.max_request_bytes <= 0:
            raise ValueError("max_request_bytes debe ser mayor que cero")
        if not 1 <= self.api_port <= 65535:
            raise ValueError("api_port debe estar entre 1 y 65535")
        return self


settings = Settings()
