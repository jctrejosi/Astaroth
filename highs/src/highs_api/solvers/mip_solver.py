"""Resolución de MIP: integralidad, cotas efectivas de binarias y incumbentes."""

from __future__ import annotations

from ..core import converters
from ..core.validators import validate_mip_request
from ..models.common import SolveResponse
from ..models.mip import MIPRequest
from .base import execute, extract, make_response, start_engine


def solve_mip(request: MIPRequest) -> SolveResponse:
    """Flujo completo de resolución de un MIP.

    Una solución factible puede existir aunque no se haya probado optimalidad;
    el estado y el mensaje distinguen ambos casos, y la extracción depende de
    las banderas de validez del motor.
    """
    lowers, uppers = validate_mip_request(request)

    engine = start_engine()
    converters.apply_mip_options(engine, request.options)
    converters.build_columns(engine, request.objective, lowers, uppers)
    converters.apply_objective_sense(engine, request.objective.sense)
    converters.apply_integrality(engine, request.integrality)
    converters.add_constraints(engine, request.constraints)

    status, solve_time_ms = execute(engine)
    extract_result = extract(engine, "MIP", status)
    return make_response(
        status=status,
        extract_result=extract_result,
        solver_used="mip",
        solve_time_ms=solve_time_ms,
    )
