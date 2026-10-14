"""Resolución de QP convexo de minimización con solver activo-set (``qpasm``)."""

from __future__ import annotations

from ..core import converters
from ..core.validators import resolve_bounds, validate_qp_request
from ..models.common import SolveResponse, SolverUsed
from ..models.qp import QPRequest
from .base import execute, extract, make_response, start_engine

_QP_SOLVER_USED: dict[str, SolverUsed] = {
    "qpasm": "qpasm",
    "choose": "auto",
}


def solve_qp(request: QPRequest) -> SolveResponse:
    """Flujo completo de resolución de un QP convexo.

    ``solver="qp"`` no se usa nunca: no es una opción válida en la versión
    fijada de HiGHS. La Hessiana se pasa antes de añadir las filas, con formato
    triangular explícito.
    """
    validate_qp_request(request)

    engine = start_engine()
    converters.apply_qp_options(engine, request.options)
    lowers, uppers = resolve_bounds(request.bounds, request.n_variables)
    converters.build_columns(engine, request.objective, lowers, uppers)
    converters.apply_objective_sense(engine, request.objective.sense)
    converters.add_hessian(engine, request.q)
    converters.add_constraints(engine, request.constraints)

    status, solve_time_ms = execute(engine)
    extract_result = extract(engine, "QP", status)
    return make_response(
        status=status,
        extract_result=extract_result,
        solver_used=_QP_SOLVER_USED[request.options.solver],
        solve_time_ms=solve_time_ms,
    )
