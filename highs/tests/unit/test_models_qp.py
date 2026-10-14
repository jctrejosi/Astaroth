"""Validaciones del contrato QP: dimensiones, sentido y propiedades de Q."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from highs_api.config import settings
from highs_api.core.exceptions import ModelValidationError
from highs_api.core.validators import validate_qp_request
from highs_api.models.qp import QPRequest


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "objective": {"sense": "minimize", "coefficients": [0.0, 0.0]},
        "Q": [[2.0, 0.0], [0.0, 4.0]],
    }
    base.update(overrides)
    return base


def test_rechaza_q_no_cuadrada() -> None:
    with pytest.raises(ValidationError):
        QPRequest.model_validate(_payload(Q=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]))


def test_rechaza_q_de_dimension_incorrecta() -> None:
    with pytest.raises(ValidationError):
        QPRequest.model_validate(_payload(Q=[[1.0]]))


def test_rechaza_fila_de_q_con_longitud_incorrecta() -> None:
    with pytest.raises(ValidationError):
        QPRequest.model_validate(_payload(Q=[[1.0, 0.0], [0.0]]))


def test_rechaza_q_no_simetrica() -> None:
    request = QPRequest.model_validate(_payload(Q=[[1.0, 2.0], [0.0, 1.0]]))
    with pytest.raises(ModelValidationError):
        validate_qp_request(request)


def test_rechaza_q_no_psd() -> None:
    # Autovalores 3 y -1: claramente indefinida.
    request = QPRequest.model_validate(_payload(Q=[[1.0, 2.0], [2.0, 1.0]]))
    with pytest.raises(ModelValidationError):
        validate_qp_request(request)


def test_rechaza_maximize_en_qp_v1() -> None:
    with pytest.raises(ValidationError):
        QPRequest.model_validate(_payload(objective={"sense": "maximize", "coefficients": [0, 0]}))


def test_rechaza_qp_que_excede_max_qp_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "max_qp_variables", 2)
    n = 3
    identity = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    request = QPRequest.model_validate(_payload(objective={"coefficients": [0.0] * n}, Q=identity))
    with pytest.raises(ModelValidationError):
        validate_qp_request(request)


def test_acepta_qp_psd_valido() -> None:
    request = QPRequest.model_validate(_payload())
    validate_qp_request(request)
    assert request.q == [[2.0, 0.0], [0.0, 4.0]]
