"""Tipos públicos compartidos: enums, objetivos, restricciones, cotas y respuestas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Números estrictos: sin coerción ambigua de strings y siempre finitos.
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0.0)]
NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]

SolverUsed = Literal["simplex", "ipm", "auto", "mip", "qpasm"]


class APIModel(BaseModel):
    """Base de los contratos públicos: sin campos extra y con números estrictos."""

    model_config = ConfigDict(extra="forbid")


class Sense(StrEnum):
    """Sentido del objetivo."""

    minimize = "minimize"
    maximize = "maximize"


class ConstraintSense(StrEnum):
    """Sentido de una restricción lineal."""

    le = "<="
    ge = ">="
    eq = "="


class VariableType(StrEnum):
    """Tipo de variable admitido por el contrato público."""

    continuous = "continuous"
    integer = "integer"
    binary = "binary"


class SolverStatus(StrEnum):
    """Estado normalizado de la resolución, independiente del código HTTP."""

    optimal = "optimal"
    infeasible = "infeasible"
    unbounded = "unbounded"
    unbounded_or_infeasible = "unbounded_or_infeasible"
    time_limit = "time_limit"
    iteration_limit = "iteration_limit"
    solution_limit = "solution_limit"
    objective_bound = "objective_bound"
    objective_target = "objective_target"
    interrupted = "interrupted"
    memory_limit = "memory_limit"
    unknown = "unknown"


class PresolveMode(StrEnum):
    """Modo de presolve expuesto al cliente."""

    on = "on"
    off = "off"
    choose = "choose"


class Objective(APIModel):
    """Objetivo lineal `min/max c^T x`; la longitud define el número de variables."""

    sense: Sense = Sense.minimize
    coefficients: list[FiniteFloat] = Field(min_length=1)


class Constraint(APIModel):
    """Restricción lineal densa `coeffs^T x {<=,>=,=} rhs`."""

    coefficients: list[FiniteFloat]
    sense: ConstraintSense
    rhs: FiniteFloat


class Bound(APIModel):
    """Cotas de una variable.

    `lower` omitido vale ``0`` y ``lower: null`` significa −∞. `upper` omitido
    o ``null`` significa +∞.
    """

    lower: FiniteFloat | None = 0.0
    upper: FiniteFloat | None = None

    @model_validator(mode="after")
    def _check_order(self) -> Bound:
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("cota inválida: lower no puede superar a upper")
        return self


class CommonOptions(APIModel):
    """Opciones comunes a los tres tipos de problema."""

    time_limit: NonNegativeFloat | None = None
    threads: NonNegativeInt | None = None
    presolve: PresolveMode = PresolveMode.choose


class LPOptions(CommonOptions):
    solver: Literal["simplex", "ipm", "choose"] = "choose"


class MIPOptions(CommonOptions):
    mip_rel_gap: NonNegativeFloat | None = None
    random_seed: NonNegativeInt | None = None


class QPOptions(CommonOptions):
    solver: Literal["qpasm", "choose"] = "qpasm"
    qp_iteration_limit: NonNegativeInt | None = None


class SolverMetadata(APIModel):
    """Metadatos del solve; los datos no disponibles se devuelven como ``null``."""

    solve_time_ms: NonNegativeFloat | None = None
    iterations: NonNegativeInt | None = None
    nodes_explored: NonNegativeInt | None = None
    gap: NonNegativeFloat | None = None
    solver_used: SolverUsed
    engine_version: str


class SolveResponse(APIModel):
    """Respuesta común de LP, MIP y QP; los campos no aplicables van en ``null``."""

    status: SolverStatus
    objective_value: FiniteFloat | None = None
    variables: list[FiniteFloat] | None = None
    dual_values: list[FiniteFloat] | None = None
    reduced_costs: list[FiniteFloat] | None = None
    metadata: SolverMetadata
    message: str | None = None


class EngineInfo(APIModel):
    name: str
    version: str


class LimitsInfo(APIModel):
    max_variables: int
    max_constraints: int
    max_matrix_elements: int
    max_qp_variables: int
    max_request_bytes: int
    max_time_limit_seconds: float


class CapabilitiesResponse(APIModel):
    """Declaración verificable de capacidades, límites y limitaciones."""

    name: str
    api_version: str
    service_version: str
    engine: EngineInfo
    problem_types: list[str]
    constraint_types: list[str]
    variable_types_by_problem: dict[str, list[str]]
    options_by_problem: dict[str, list[str]]
    limits: LimitsInfo
    limitations: list[str]


def validate_common_dimensions(
    n_variables: int,
    constraints: list[Constraint],
    bounds: list[Bound] | None,
) -> None:
    """Validación estructural compartida por LP, MIP y QP.

    Cada restricción debe tener exactamente un coeficiente por variable y, si
    se envían cotas, exactamente una entrada por variable.
    """

    for index, constraint in enumerate(constraints):
        if len(constraint.coefficients) != n_variables:
            raise ValueError(
                f"la restricción {index} debe tener {n_variables} coeficientes "
                f"(recibidos {len(constraint.coefficients)})"
            )
    if bounds is not None and len(bounds) != n_variables:
        raise ValueError(f"bounds debe tener {n_variables} elementos (recibidos {len(bounds)})")
