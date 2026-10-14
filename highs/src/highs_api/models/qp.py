"""Contrato del problema QP convexo: objetivo cuadrático de minimización."""

from __future__ import annotations

from pydantic import ConfigDict, Field, model_validator

from .common import (
    APIModel,
    Bound,
    Constraint,
    FiniteFloat,
    Objective,
    QPOptions,
    Sense,
    validate_common_dimensions,
)


class QPRequest(APIModel):
    """Modelo QP: ``min 0.5 * x^T Q x + c^T x`` con `Q` densa y simétrica.

    La versión 1 solo admite minimización; el sentido `maximize` se rechaza.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    objective: Objective
    q: list[list[FiniteFloat]] = Field(alias="Q")
    constraints: list[Constraint] = Field(default_factory=list)
    bounds: list[Bound] | None = None
    options: QPOptions = Field(default_factory=QPOptions)

    @property
    def n_variables(self) -> int:
        return len(self.objective.coefficients)

    @model_validator(mode="after")
    def _validate_dimensions(self) -> QPRequest:
        if self.objective.sense is not Sense.minimize:
            raise ValueError("QP v1 solo admite minimización convexa (sense='minimize')")
        n_variables = self.n_variables
        if len(self.q) != n_variables:
            raise ValueError(
                f"Q debe ser de {n_variables}x{n_variables} (recibidas {len(self.q)} filas)"
            )
        for row_index, row in enumerate(self.q):
            if len(row) != n_variables:
                raise ValueError(
                    f"la fila {row_index} de Q debe tener {n_variables} elementos "
                    f"(recibidos {len(row)})"
                )
        validate_common_dimensions(n_variables, self.constraints, self.bounds)
        return self
