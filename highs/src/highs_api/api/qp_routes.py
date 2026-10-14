"""Endpoint de resolución QP."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.logging import get_logger
from ..models.common import SolveResponse
from ..models.qp import QPRequest
from ..solvers.qp_solver import solve_qp

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/qp", tags=["QP"])


@router.post("/solve", response_model=SolveResponse, summary="Resolver un QP convexo")
def post_solve(request: QPRequest) -> SolveResponse:
    """Resuelve un QP convexo de minimización y devuelve la respuesta pública común."""
    response = solve_qp(request)
    logger.info(
        "solve_result",
        extra={
            "problem_type": "QP",
            "n_variables": request.n_variables,
            "n_constraints": len(request.constraints),
            "solver_status": response.status.value,
            "solve_time_ms": response.metadata.solve_time_ms,
            "engine_version": response.metadata.engine_version,
        },
    )
    return response
