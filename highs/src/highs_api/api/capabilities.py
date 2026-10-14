"""Declaración verificable de capacidades, límites y limitaciones del motor."""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..config import settings
from ..core.converters import engine_version
from ..models.common import CapabilitiesResponse, EngineInfo, LimitsInfo

router = APIRouter(prefix="/v1", tags=["capabilities"])

_LIMITATIONS = [
    "QP v1 solo admite minimización convexa con Q positiva semidefinida.",
    "No MIQP ni MIQCP.",
    "No NLP ni restricciones cuadráticas.",
    "No hay jobs asíncronos ni persistencia.",
]


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="Capacidades del motor",
)
def get_capabilities() -> CapabilitiesResponse:
    """Capacidades comprobadas contra la versión instalada, no una lista inventada.

    Los límites reflejan la configuración en ejecución y la versión del motor
    se obtiene de ``highspy`` en tiempo de ejecución.
    """
    return CapabilitiesResponse(
        name="highs",
        api_version="v1",
        service_version=__version__,
        engine=EngineInfo(name="HiGHS", version=engine_version()),
        problem_types=["LP", "MIP", "QP"],
        constraint_types=["<=", ">=", "="],
        variable_types_by_problem={
            "LP": ["continuous"],
            "MIP": ["continuous", "integer", "binary"],
            "QP": ["continuous"],
        },
        options_by_problem={
            "LP": ["solver", "presolve", "time_limit", "threads"],
            "MIP": ["presolve", "time_limit", "threads", "mip_rel_gap", "random_seed"],
            "QP": ["solver", "presolve", "time_limit", "threads", "qp_iteration_limit"],
        },
        limits=LimitsInfo(
            max_variables=settings.max_variables,
            max_constraints=settings.max_constraints,
            max_matrix_elements=settings.max_matrix_elements,
            max_qp_variables=settings.max_qp_variables,
            max_request_bytes=settings.max_request_bytes,
            max_time_limit_seconds=settings.max_time_limit_seconds,
        ),
        limitations=_LIMITATIONS,
    )
