"""Límites de recursos, opciones y validación numérica de Q."""

from __future__ import annotations

import pytest

from highs_api.config import settings
from highs_api.core.exceptions import ModelValidationError
from highs_api.core.validators import (
    count_matrix_elements,
    validate_lp_request,
    validate_qp_matrix,
    validate_qp_request,
)
from highs_api.models.common import Constraint, ConstraintSense
from highs_api.models.lp import LPRequest
from highs_api.models.qp import QPRequest


def _lp(n_variables: int, n_constraints: int = 0, **options: object) -> LPRequest:
    constraints = [
        {"coefficients": [1.0] * n_variables, "sense": ">=", "rhs": 1.0}
        for _ in range(n_constraints)
    ]
    return LPRequest.model_validate(
        {
            "objective": {"coefficients": [1.0] * n_variables},
            "constraints": constraints,
            "options": options,
        }
    )


def test_limite_de_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_variables", 2)
    validate_lp_request(_lp(2))
    with pytest.raises(ModelValidationError):
        validate_lp_request(_lp(3))


def test_limite_de_restricciones(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_constraints", 1)
    validate_lp_request(_lp(2, n_constraints=1))
    with pytest.raises(ModelValidationError):
        validate_lp_request(_lp(2, n_constraints=2))


def test_limite_de_elementos_de_matriz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_matrix_elements", 3)
    validate_lp_request(_lp(2, n_constraints=1))
    with pytest.raises(ModelValidationError):
        validate_lp_request(_lp(4, n_constraints=2))


def test_conteo_de_elementos_solo_considera_no_nulos() -> None:
    constraints = [
        Constraint(coefficients=[1.0, 0.0, 2.0], sense=ConstraintSense.le, rhs=1.0),
        Constraint(coefficients=[0.0, 0.0, 0.0], sense=ConstraintSense.le, rhs=1.0),
    ]
    assert count_matrix_elements(constraints) == 2


def test_limite_de_tiempo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_time_limit_seconds", 10.0)
    validate_lp_request(_lp(1, time_limit=10))
    with pytest.raises(ModelValidationError):
        validate_lp_request(_lp(1, time_limit=11))


def test_limite_de_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_threads", 4)
    monkeypatch.setattr(settings, "default_threads", 0)
    validate_lp_request(_lp(1, threads=4))
    with pytest.raises(ModelValidationError):
        validate_lp_request(_lp(1, threads=5))

    # El default también se valida (si la configuración fuera inconsistente).
    monkeypatch.setattr(settings, "default_threads", 6)
    with pytest.raises(ModelValidationError):
        validate_lp_request(_lp(1))


def test_validacion_simetria_y_psd() -> None:
    validate_qp_matrix([[2.0, 0.5], [0.5, 3.0]])

    with pytest.raises(ModelValidationError):
        validate_qp_matrix([[1.0, 0.5], [0.0, 1.0]])

    with pytest.raises(ModelValidationError):
        validate_qp_matrix([[1.0, 2.0], [2.0, 1.0]])

    # Matriz singular (autovalor 0) es PSD válida.
    validate_qp_matrix([[1.0, 1.0], [1.0, 1.0]])

    # Tolerancia relativa a la escala: asimetría 1e-7 con entradas ~1e5 es aceptada.
    validate_qp_matrix([[100000.0, 99999.9999999], [99999.9999999, 100000.0]])


def test_limite_qp_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_qp_variables", 1)
    request = QPRequest.model_validate({"objective": {"coefficients": [0.0]}, "Q": [[1.0]]})
    validate_qp_request(request)

    request = QPRequest.model_validate(
        {"objective": {"coefficients": [0.0, 0.0]}, "Q": [[1.0, 0.0], [0.0, 1.0]]}
    )
    with pytest.raises(ModelValidationError):
        validate_qp_request(request)
