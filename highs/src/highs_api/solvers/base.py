"""Utilidades comunes reales de los solvers: instancia, ejecución y respuesta.

No hay una clase base vacía: solo lo que LP, MIP y QP comparten de verdad.
"""

from __future__ import annotations

import time

import highspy

from ..core.converters import (
    ProblemKind,
    SolveExtract,
    build_response,
    create_engine,
    extract_solution,
    map_status,
    require_status,
)
from ..models.common import SolveResponse, SolverStatus, SolverUsed


def start_engine() -> highspy.Highs:
    """Crea una instancia nueva por request; no se comparte estado mutable."""
    return create_engine()


def execute(engine: highspy.Highs) -> tuple[SolverStatus, float]:
    """Ejecuta ``run()``, comprueba su ``HighsStatus`` y mide el tiempo de solve.

    El tiempo medido cubre únicamente la resolución, no la conversión previa ni
    la serialización posterior.
    """
    started = time.perf_counter()
    status_code = engine.run()
    solve_time_ms = (time.perf_counter() - started) * 1000.0
    require_status(status_code, "run")
    return map_status(engine.getModelStatus()), solve_time_ms


def extract(engine: highspy.Highs, problem: ProblemKind, status: SolverStatus) -> SolveExtract:
    return extract_solution(engine, problem=problem, status=status)


def make_response(
    *,
    status: SolverStatus,
    extract_result: SolveExtract,
    solver_used: SolverUsed,
    solve_time_ms: float,
) -> SolveResponse:
    return build_response(
        status=status,
        extract=extract_result,
        solver_used=solver_used,
        solve_time_ms=solve_time_ms,
    )
