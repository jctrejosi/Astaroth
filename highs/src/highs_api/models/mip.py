"""Contrato del problema MIP: variables continuas, enteras y binarias."""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import (
    APIModel,
    Bound,
    Constraint,
    MIPOptions,
    Objective,
    VariableType,
    validate_common_dimensions,
)


class MIPRequest(APIModel):
    """Modelo MIP: objetivo y restricciones lineales con `integrality` obligatoria."""

    objective: Objective
    constraints: list[Constraint] = Field(default_factory=list)
    bounds: list[Bound] | None = None
    integrality: list[VariableType]
    options: MIPOptions = Field(default_factory=MIPOptions)

    @property
    def n_variables(self) -> int:
        return len(self.objective.coefficients)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> MIPRequest:
        validate_common_dimensions(self.n_variables, self.constraints, self.bounds)
        if len(self.integrality) != self.n_variables:
            raise ValueError(
                f"integrality debe tener {self.n_variables} elementos "
                f"(recibidos {len(self.integrality)})"
            )
        return self
