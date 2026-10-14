"""Endpoint de resolución MIP."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.logging import get_logger
from ..models.common import SolveResponse
from ..models.mip import MIPRequest
from ..solvers.mip_solver import solve_mip

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/mip", tags=["MIP"])


@router.post("/solve", response_model=SolveResponse, summary="Resolver un MIP")
def post_solve(request: MIPRequest) -> SolveResponse:
    """Resuelve un MIP y devuelve la respuesta pública común."""
    response = solve_mip(request)
    logger.info(
        "solve_result",
        extra={
            "problem_type": "MIP",
            "n_variables": request.n_variables,
            "n_constraints": len(request.constraints),
            "solver_status": response.status.value,
            "solve_time_ms": response.metadata.solve_time_ms,
            "engine_version": response.metadata.engine_version,
        },
    )
    return response
