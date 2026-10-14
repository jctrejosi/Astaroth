"""Endpoint de resolución LP."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.logging import get_logger
from ..models.common import SolveResponse
from ..models.lp import LPRequest
from ..solvers.lp_solver import solve_lp

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/lp", tags=["LP"])


@router.post("/solve", response_model=SolveResponse, summary="Resolver un LP")
def post_solve(request: LPRequest) -> SolveResponse:
    """Resuelve un LP y devuelve la respuesta pública común."""
    response = solve_lp(request)
    logger.info(
        "solve_result",
        extra={
            "problem_type": "LP",
            "n_variables": request.n_variables,
            "n_constraints": len(request.constraints),
            "solver_status": response.status.value,
            "solve_time_ms": response.metadata.solve_time_ms,
            "engine_version": response.metadata.engine_version,
        },
    )
    return response
