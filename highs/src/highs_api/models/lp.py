"""Contrato del problema LP: variables continuas, objetivo y restricciones lineales."""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import APIModel, Bound, Constraint, LPOptions, Objective, validate_common_dimensions


class LPRequest(APIModel):
    """Modelo LP: sin integralidad ni matriz Q; todas las variables son continuas."""

    objective: Objective
    constraints: list[Constraint] = Field(default_factory=list)
    bounds: list[Bound] | None = None
    options: LPOptions = Field(default_factory=LPOptions)

    @property
    def n_variables(self) -> int:
        return len(self.objective.coefficients)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> LPRequest:
        validate_common_dimensions(self.n_variables, self.constraints, self.bounds)
        return self
