"""Resolución de LP: validación semántica, conversión, ``run()`` y respuesta común."""

from __future__ import annotations

from ..core import converters
from ..core.validators import resolve_bounds, validate_lp_request
from ..models.common import SolveResponse, SolverUsed
from ..models.lp import LPRequest
from .base import execute, extract, make_response, start_engine

_LP_SOLVER_USED: dict[str, SolverUsed] = {
    "simplex": "simplex",
    "ipm": "ipm",
    "choose": "auto",
}


def solve_lp(request: LPRequest) -> SolveResponse:
    """Flujo completo de resolución de un LP."""
    validate_lp_request(request)

    engine = start_engine()
    converters.apply_lp_options(engine, request.options)
    lowers, uppers = resolve_bounds(request.bounds, request.n_variables)
    converters.build_columns(engine, request.objective, lowers, uppers)
    converters.apply_objective_sense(engine, request.objective.sense)
    converters.add_constraints(engine, request.constraints)

    status, solve_time_ms = execute(engine)
    extract_result = extract(engine, "LP", status)
    return make_response(
        status=status,
        extract_result=extract_result,
        solver_used=_LP_SOLVER_USED[request.options.solver],
        solve_time_ms=solve_time_ms,
    )
