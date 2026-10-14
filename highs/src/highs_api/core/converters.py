"""Conversión entre los modelos públicos y la API de ``highspy``.

Ningún tipo de ``highspy`` sale de este módulo hacia las respuestas HTTP: aquí
se construye el modelo en el motor, se mapean estados explícitamente y se
normalizan los resultados (incluidos los valores no finitos, que nunca se
serializan como números JSON).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

import highspy
import numpy as np

from ..config import settings
from ..models.common import (
    CommonOptions,
    Constraint,
    ConstraintSense,
    LPOptions,
    MIPOptions,
    Objective,
    QPOptions,
    Sense,
    SolveResponse,
    SolverMetadata,
    SolverStatus,
    SolverUsed,
    VariableType,
)
from .exceptions import SolverExecutionError

ProblemKind = Literal["LP", "MIP", "QP"]

_INFINITY = highspy.kHighsInf


@lru_cache(maxsize=1)
def engine_version() -> str:
    """Versión de HiGHS en tiempo de ejecución (nunca hardcodeada)."""
    return str(highspy.Highs().version())


def require_status(status: highspy.HighsStatus, context: str) -> None:
    """Comprueba el ``HighsStatus`` de una llamada que modifica modelo u opciones."""
    if status == highspy.HighsStatus.kError:
        raise SolverExecutionError(f"HiGHS rechazó la operación '{context}'.")


def set_engine_option(engine: highspy.Highs, name: str, value: bool | int | float | str) -> None:
    require_status(engine.setOptionValue(name, value), f"opción '{name}'")


def create_engine() -> highspy.Highs:
    """Crea una instancia nueva de HiGHS por request; no se comparte estado mutable."""
    engine = highspy.Highs()
    set_engine_option(engine, "output_flag", settings.output_flag)
    return engine


def resolve_threads(options: CommonOptions) -> int:
    """``0``/omitido solicitan modo automático; el servicio lo fija al máximo configurado."""
    raw = options.threads if options.threads is not None else settings.default_threads
    return settings.max_threads if raw == 0 else raw


def resolve_time_limit(options: CommonOptions) -> float:
    """``null`` usa ``HIGHS_DEFAULT_TIME_LIMIT``."""
    return options.time_limit if options.time_limit is not None else settings.default_time_limit


def _apply_common_options(engine: highspy.Highs, options: CommonOptions) -> None:
    set_engine_option(engine, "time_limit", resolve_time_limit(options))
    set_engine_option(engine, "threads", resolve_threads(options))
    set_engine_option(engine, "presolve", options.presolve.value)


def apply_lp_options(engine: highspy.Highs, options: LPOptions) -> None:
    _apply_common_options(engine, options)
    set_engine_option(engine, "solver", options.solver)


def apply_mip_options(engine: highspy.Highs, options: MIPOptions) -> None:
    _apply_common_options(engine, options)
    if options.mip_rel_gap is not None:
        set_engine_option(engine, "mip_rel_gap", options.mip_rel_gap)
    if options.random_seed is not None:
        set_engine_option(engine, "random_seed", options.random_seed)


def apply_qp_options(engine: highspy.Highs, options: QPOptions) -> None:
    _apply_common_options(engine, options)
    # `qp` no es una opción válida en la versión fijada de HiGHS; `qpasm` sí.
    set_engine_option(engine, "solver", options.solver)
    if options.qp_iteration_limit is not None:
        set_engine_option(engine, "qp_iteration_limit", options.qp_iteration_limit)


def build_columns(
    engine: highspy.Highs,
    objective: Objective,
    lowers: list[float],
    uppers: list[float],
) -> None:
    """Crea las variables con sus costos y cotas, antes de cualquier fila."""
    require_status(
        engine.addCols(
            len(objective.coefficients),
            list(objective.coefficients),
            lowers,
            uppers,
            0,
            [],
            [],
            [],
        ),
        "addCols",
    )


def apply_objective_sense(engine: highspy.Highs, sense: Sense) -> None:
    target = highspy.ObjSense.kMaximize if sense is Sense.maximize else highspy.ObjSense.kMinimize
    require_status(engine.changeObjectiveSense(target), "changeObjectiveSense")


def integrality_arrays(
    integrality: list[VariableType],
) -> tuple[list[int], list[highspy.HighsVarType]]:
    """Índices de variables no continuas y su tipo interno (enteras)."""
    indices = [
        index for index, kind in enumerate(integrality) if kind is not VariableType.continuous
    ]
    kinds = [highspy.HighsVarType.kInteger] * len(indices)
    return indices, kinds


def apply_integrality(engine: highspy.Highs, integrality: list[VariableType]) -> None:
    """Marca como enteras las variables ``integer`` y ``binary``.

    Las binarias ya llegan con cotas efectivas dentro de ``[0, 1]``; aquí solo
    se declara su integralidad.
    """
    indices, kinds = integrality_arrays(integrality)
    if not indices:
        return
    require_status(
        engine.changeColsIntegrality(
            len(indices),
            np.asarray(indices, dtype=np.int32),
            np.asarray([int(kind) for kind in kinds], dtype=np.uint8),
        ),
        "changeColsIntegrality",
    )


def constraint_row_bounds(constraint: Constraint) -> tuple[float, float]:
    """Convierte ``<=``, ``>=`` y ``=`` en límites inferior/superior de fila."""
    if constraint.sense is ConstraintSense.le:
        return -_INFINITY, constraint.rhs
    if constraint.sense is ConstraintSense.ge:
        return constraint.rhs, _INFINITY
    return constraint.rhs, constraint.rhs


def add_constraints(engine: highspy.Highs, constraints: list[Constraint]) -> None:
    """Añade las filas en formato disperso por filas (los ceros se omiten).

    No se aplica ningún umbral de sparsificación: solo se omiten ceros exactos.
    """
    if not constraints:
        return
    row_lower: list[float] = []
    row_upper: list[float] = []
    starts: list[int] = [0]
    indices: list[int] = []
    values: list[float] = []
    for constraint in constraints:
        lower, upper = constraint_row_bounds(constraint)
        row_lower.append(lower)
        row_upper.append(upper)
        for column, coefficient in enumerate(constraint.coefficients):
            if coefficient != 0.0:
                indices.append(column)
                values.append(coefficient)
        starts.append(len(indices))
    require_status(
        engine.addRows(
            len(constraints), row_lower, row_upper, len(indices), starts, indices, values
        ),
        "addRows",
    )


def hessian_csc(matrix: list[list[float]]) -> tuple[list[int], list[int], list[float]]:
    """Extrae una sola mitad triangular de Q en formato CSC (columna a columna).

    Para una Q simétrica, almacenar el triángulo inferior describe exactamente
    la misma matriz. ``start`` es monótono, cada índice de fila es válido y la
    cantidad de elementos coincide con ``len(value)``.
    """
    start = [0]
    index: list[int] = []
    value: list[float] = []
    for column in range(len(matrix)):
        for row in range(column, len(matrix)):
            entry = matrix[row][column]
            if entry != 0.0:
                index.append(row)
                value.append(entry)
        start.append(len(index))
    return start, index, value


def add_hessian(engine: highspy.Highs, matrix: list[list[float]]) -> None:
    """Pasa la Hessiana a HiGHS con su formato triangular explícito."""
    start, index, value = hessian_csc(matrix)
    require_status(
        engine.passHessian(
            len(matrix),
            len(value),
            int(highspy.HessianFormat.kTriangular),
            start,
            index,
            value,
        ),
        "passHessian",
    )


# Mapeo explícito desde los enums de la versión fijada; nunca por texto.
_STATUS_MAP: dict[highspy.HighsModelStatus, SolverStatus] = {
    highspy.HighsModelStatus.kNotset: SolverStatus.unknown,
    highspy.HighsModelStatus.kModelEmpty: SolverStatus.unknown,
    highspy.HighsModelStatus.kOptimal: SolverStatus.optimal,
    highspy.HighsModelStatus.kInfeasible: SolverStatus.infeasible,
    highspy.HighsModelStatus.kUnboundedOrInfeasible: SolverStatus.unbounded_or_infeasible,
    highspy.HighsModelStatus.kUnbounded: SolverStatus.unbounded,
    highspy.HighsModelStatus.kObjectiveBound: SolverStatus.objective_bound,
    highspy.HighsModelStatus.kObjectiveTarget: SolverStatus.objective_target,
    highspy.HighsModelStatus.kTimeLimit: SolverStatus.time_limit,
    highspy.HighsModelStatus.kIterationLimit: SolverStatus.iteration_limit,
    highspy.HighsModelStatus.kSolutionLimit: SolverStatus.solution_limit,
    highspy.HighsModelStatus.kInterrupt: SolverStatus.interrupted,
    # `kHighsInterrupt` existe en runtime pero falta en los stubs de la versión fijada.
    highspy.HighsModelStatus.kHighsInterrupt: SolverStatus.interrupted,  # type: ignore[attr-defined]
    highspy.HighsModelStatus.kMemoryLimit: SolverStatus.memory_limit,
    highspy.HighsModelStatus.kUnknown: SolverStatus.unknown,
}

_SOLVER_ERROR_STATUSES = frozenset(
    {
        highspy.HighsModelStatus.kLoadError,
        highspy.HighsModelStatus.kModelError,
        highspy.HighsModelStatus.kPresolveError,
        highspy.HighsModelStatus.kSolveError,
        highspy.HighsModelStatus.kPostsolveError,
    }
)


def map_status(model_status: highspy.HighsModelStatus) -> SolverStatus:
    """Mapea ``HighsModelStatus`` al estado público mediante una tabla explícita."""
    if model_status in _SOLVER_ERROR_STATUSES:
        raise SolverExecutionError(
            f"HiGHS reportó un estado de error interno ({model_status.name})"
        )
    mapped = _STATUS_MAP.get(model_status)
    if mapped is None:
        raise SolverExecutionError(
            f"estado de HiGHS no reconocido por esta versión del contrato ({model_status.name})"
        )
    return mapped


@dataclass(frozen=True)
class SolveExtract:
    """Datos extraídos del motor, ya normalizados para el contrato público."""

    objective_value: float | None
    variables: list[float] | None
    dual_values: list[float] | None
    reduced_costs: list[float] | None
    iterations: int | None
    nodes_explored: int | None
    gap: float | None


# Estados que pueden portar una solución con significado: un óptimo o un
# incumbente bajo un límite. Infactible, no acotado y desconocido no llevan
# solución aunque el motor tenga un punto interno con `value_valid=True`.
_SOLUTION_BEARING_STATUSES = frozenset(
    {
        SolverStatus.optimal,
        SolverStatus.time_limit,
        SolverStatus.iteration_limit,
        SolverStatus.solution_limit,
        SolverStatus.objective_bound,
        SolverStatus.objective_target,
        SolverStatus.interrupted,
    }
)


def finite_or_none(value: float | int | None) -> float | None:
    """Convierte centinelas y valores no finitos del motor en ``None``."""
    if value is None:
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def finite_vector_or_none(values: Iterable[float]) -> list[float] | None:
    """Devuelve el vector solo si todos sus elementos son finitos."""
    result = [float(value) for value in values]
    if all(math.isfinite(value) for value in result):
        return result
    return None


def _non_negative_or_none(value: int | None) -> int | None:
    if value is None:
        return None
    integer = int(value)
    return integer if integer >= 0 else None


def _aggregate_counts(*counts: int) -> int | None:
    valid = [int(count) for count in counts if int(count) >= 0]
    return sum(valid) if valid else None


def extract_solution(
    engine: highspy.Highs, *, problem: ProblemKind, status: SolverStatus
) -> SolveExtract:
    """Extrae solución y métricas solo cuando HiGHS las marca como válidas.

    Una solución puede existir aunque el estado sea un límite (``time_limit`` u
    otro); la extracción depende de las banderas de validez del motor y de que
    el estado pueda portar una solución (óptimo o incumbente bajo límite).
    """
    solution = engine.getSolution()
    info = engine.getInfo()

    solution_bearing = status in _SOLUTION_BEARING_STATUSES
    value_valid = bool(solution.value_valid) and solution_bearing
    dual_valid = bool(solution.dual_valid) and solution_bearing

    objective_value = finite_or_none(engine.getObjectiveValue()) if value_valid else None
    variables = finite_vector_or_none(solution.col_value) if value_valid else None
    if variables is None:
        # Sin vector de variables finito no se reporta tampoco el objetivo.
        objective_value = None

    dual_values: list[float] | None = None
    reduced_costs: list[float] | None = None
    if dual_valid and problem in ("LP", "QP"):
        dual_values = finite_vector_or_none(solution.row_dual)
        reduced_costs = finite_vector_or_none(solution.col_dual)

    iterations: int | None
    if problem == "QP":
        iterations = _aggregate_counts(info.qp_iteration_count)
    elif problem == "MIP":
        iterations = _aggregate_counts(info.simplex_iteration_count)
    else:
        iterations = _aggregate_counts(
            info.simplex_iteration_count,
            info.ipm_iteration_count,
            info.crossover_iteration_count,
        )

    nodes_explored = _non_negative_or_none(info.mip_node_count) if problem == "MIP" else None
    gap = finite_or_none(info.mip_gap) if problem == "MIP" else None
    if gap is not None and gap < 0.0:
        gap = None

    return SolveExtract(
        objective_value=objective_value,
        variables=variables,
        dual_values=dual_values,
        reduced_costs=reduced_costs,
        iterations=iterations,
        nodes_explored=nodes_explored,
        gap=gap,
    )


_STATUS_MESSAGES: dict[SolverStatus, str] = {
    SolverStatus.infeasible: "El modelo es infactible.",
    SolverStatus.unbounded: "El modelo no está acotado.",
    SolverStatus.unbounded_or_infeasible: "El modelo es no acotado o infactible.",
    SolverStatus.time_limit: "Se alcanzó el límite de tiempo.",
    SolverStatus.iteration_limit: "Se alcanzó el límite de iteraciones.",
    SolverStatus.solution_limit: "Se alcanzó el límite de soluciones.",
    SolverStatus.objective_bound: "Se alcanzó la cota de objetivo.",
    SolverStatus.objective_target: "Se alcanzó el objetivo deseado.",
    SolverStatus.interrupted: "La resolución fue interrumpida.",
    SolverStatus.memory_limit: "Se alcanzó el límite de memoria.",
    SolverStatus.unknown: "El motor no determinó un estado concluyente.",
}

_LIMIT_STATUSES = frozenset(
    {
        SolverStatus.time_limit,
        SolverStatus.iteration_limit,
        SolverStatus.solution_limit,
    }
)


def build_message(status: SolverStatus, has_solution: bool) -> str | None:
    """Texto breve de resultado; sin trazas internas ni detalles del motor."""
    if status is SolverStatus.optimal:
        return None
    base = _STATUS_MESSAGES.get(status, "Estado de resolución no concluyente.")
    if status in _LIMIT_STATUSES and has_solution:
        return base + " Se devuelve la mejor solución factible encontrada."
    return base


def build_response(
    *,
    status: SolverStatus,
    extract: SolveExtract,
    solver_used: SolverUsed,
    solve_time_ms: float,
) -> SolveResponse:
    """Construye la respuesta pública común de LP, MIP y QP."""
    return SolveResponse(
        status=status,
        objective_value=extract.objective_value,
        variables=extract.variables,
        dual_values=extract.dual_values,
        reduced_costs=extract.reduced_costs,
        metadata=SolverMetadata(
            solve_time_ms=solve_time_ms,
            iterations=extract.iterations,
            nodes_explored=extract.nodes_explored,
            gap=extract.gap,
            solver_used=solver_used,
            engine_version=engine_version(),
        ),
        message=build_message(status, extract.variables is not None),
    )
