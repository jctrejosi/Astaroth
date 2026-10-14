"""Validaciones semánticas y límites de recursos previos a la conversión a HiGHS.

La validación estructural de dimensiones vive en los modelos Pydantic; aquí se
verifican límites de configuración, el dominio efectivo de las binarias y las
propiedades numéricas de la matriz Q (simetría y semidefinición positiva).
"""

from __future__ import annotations

import math

import numpy as np

from ..config import settings
from ..models.common import Bound, CommonOptions, Constraint, VariableType
from ..models.lp import LPRequest
from ..models.mip import MIPRequest
from ..models.qp import QPRequest
from .exceptions import ModelValidationError

# Rango aceptado por `random_seed` en la versión fijada de HiGHS (kHighsIInf).
MAX_RANDOM_SEED = 2**31 - 1


def count_matrix_elements(constraints: list[Constraint]) -> int:
    """Cuenta los coeficientes no nulos que se almacenarán en el motor.

    El contrato entrega vectores densos, pero solo los coeficientes no nulos
    ocupan memoria en HiGHS; este es el conteo relevante para el límite
    ``max_matrix_elements``.
    """
    return sum(1 for constraint in constraints for value in constraint.coefficients if value != 0.0)


def resolve_bounds(bounds: list[Bound] | None, n_variables: int) -> tuple[list[float], list[float]]:
    """Resuelve las cotas públicas a pares ``(lower, upper)`` con ±infinito interno.

    - ``bounds`` ausente → ``[0, +∞)`` para todas las variables.
    - ``lower`` omitido vale 0; ``lower: null`` significa −∞.
    - ``upper`` omitido o ``null`` significa +∞.
    """
    if bounds is None:
        return [0.0] * n_variables, [math.inf] * n_variables
    lowers = [-math.inf if bound.lower is None else bound.lower for bound in bounds]
    uppers = [math.inf if bound.upper is None else bound.upper for bound in bounds]
    return lowers, uppers


def _check_dimension_limits(n_variables: int, n_constraints: int, matrix_elements: int) -> None:
    if n_variables > settings.max_variables:
        raise ModelValidationError(
            f"el modelo tiene {n_variables} variables y el límite es {settings.max_variables}"
        )
    if n_constraints > settings.max_constraints:
        raise ModelValidationError(
            f"el modelo tiene {n_constraints} restricciones y el límite es "
            f"{settings.max_constraints}"
        )
    if matrix_elements > settings.max_matrix_elements:
        raise ModelValidationError(
            f"la matriz tiene {matrix_elements} elementos no nulos y el límite es "
            f"{settings.max_matrix_elements}"
        )


def _check_options_limits(options: CommonOptions) -> None:
    if options.time_limit is not None and options.time_limit > settings.max_time_limit_seconds:
        raise ModelValidationError(
            f"time_limit no puede superar {settings.max_time_limit_seconds} segundos"
        )
    raw_threads = options.threads if options.threads is not None else settings.default_threads
    if raw_threads > settings.max_threads:
        raise ModelValidationError(f"threads no puede superar {settings.max_threads}")


def validate_lp_request(request: LPRequest) -> None:
    """Validaciones semánticas del LP previas al solver."""
    _check_dimension_limits(
        request.n_variables,
        len(request.constraints),
        count_matrix_elements(request.constraints),
    )
    _check_options_limits(request.options)


def validate_mip_request(request: MIPRequest) -> tuple[list[float], list[float]]:
    """Valida el MIP y devuelve las cotas efectivas, ya restringidas por binariedad.

    Para una variable binaria el dominio efectivo es la intersección de las
    cotas del cliente con ``[0, 1]``. Si la intersección es vacía se rechaza el
    request; nunca se sobrescriben cotas silenciosamente.
    """
    _check_dimension_limits(
        request.n_variables,
        len(request.constraints),
        count_matrix_elements(request.constraints),
    )
    _check_options_limits(request.options)
    if request.options.random_seed is not None and request.options.random_seed > MAX_RANDOM_SEED:
        raise ModelValidationError(f"random_seed no puede superar {MAX_RANDOM_SEED}")

    lowers, uppers = resolve_bounds(request.bounds, request.n_variables)
    for index, variable_type in enumerate(request.integrality):
        if variable_type is not VariableType.binary:
            continue
        lower = max(lowers[index], 0.0)
        upper = min(uppers[index], 1.0)
        if lower > upper:
            raise ModelValidationError(
                f"la variable binaria {index} no tiene dominio factible: sus cotas no "
                "intersectan [0, 1]"
            )
        lowers[index] = lower
        uppers[index] = upper
    return lowers, uppers


def validate_qp_request(request: QPRequest) -> None:
    """Validaciones semánticas del QP: límite de tamaño y propiedades de Q."""
    n_variables = request.n_variables
    _check_dimension_limits(
        n_variables,
        len(request.constraints),
        count_matrix_elements(request.constraints),
    )
    if n_variables > settings.max_qp_variables:
        raise ModelValidationError(
            f"un QP admite como máximo {settings.max_qp_variables} variables "
            f"(recibidas {n_variables})"
        )
    _check_options_limits(request.options)
    validate_qp_matrix(request.q)


def validate_qp_matrix(
    matrix: list[list[float]],
    *,
    symmetry_tol: float = 1e-9,
    psd_tol: float = 1e-8,
) -> None:
    """Valida que Q sea simétrica y positiva semidefinida, sin modificarla.

    Las tolerancias son relativas a la escala de la matriz (la mayor magnitud
    de sus entradas), con un piso absoluto para matrices diminutas.
    """
    array = np.asarray(matrix, dtype=float)
    scale = float(np.max(np.abs(array))) if array.size else 0.0
    tolerance = symmetry_tol * max(1.0, scale)
    if not np.allclose(array, array.T, rtol=0.0, atol=tolerance):
        raise ModelValidationError(
            "la matriz Q debe ser simétrica (tolerancia 1e-9 relativa a su escala)"
        )
    symmetric = (array + array.T) / 2.0
    min_eigenvalue = float(np.linalg.eigvalsh(symmetric).min()) if array.size else 0.0
    if min_eigenvalue < -psd_tol * max(1.0, scale):
        raise ModelValidationError(
            "la matriz Q debe ser positiva semidefinida (tolerancia numérica 1e-8)"
        )
