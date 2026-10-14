"""Validaciones de integralidad y dominio efectivo de binarias en MIP."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from highs_api.core.exceptions import ModelValidationError
from highs_api.core.validators import validate_mip_request
from highs_api.models.mip import MIPRequest


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "objective": {"sense": "minimize", "coefficients": [1.0, 1.0]},
        "constraints": [],
        "integrality": ["integer", "continuous"],
    }
    base.update(overrides)
    return base


def test_rechaza_integrality_de_longitud_incorrecta() -> None:
    with pytest.raises(ValidationError):
        MIPRequest.model_validate(_payload(integrality=["integer"]))


def test_acepta_continuous_integer_binary() -> None:
    request = MIPRequest.model_validate(
        _payload(
            objective={"coefficients": [1.0, 1.0, 1.0]},
            integrality=["continuous", "integer", "binary"],
        )
    )
    assert [kind.value for kind in request.integrality] == ["continuous", "integer", "binary"]


def test_rechaza_tipos_de_variable_desconocidos() -> None:
    with pytest.raises(ValidationError):
        MIPRequest.model_validate(_payload(integrality=["entero", "continuous"]))


def test_binaria_sin_cotas_tiene_dominio_0_1() -> None:
    request = MIPRequest.model_validate(
        _payload(objective={"coefficients": [1.0]}, integrality=["binary"])
    )
    lowers, uppers = validate_mip_request(request)
    assert lowers == [0.0]
    assert uppers == [1.0]


def test_binaria_con_cotas_intersecta_0_1() -> None:
    request = MIPRequest.model_validate(
        _payload(
            objective={"coefficients": [1.0]},
            integrality=["binary"],
            bounds=[{"lower": 0.0, "upper": 0.5}],
        )
    )
    lowers, uppers = validate_mip_request(request)
    assert lowers == [0.0]
    assert uppers == [0.5]

    request = MIPRequest.model_validate(
        _payload(
            objective={"coefficients": [1.0]},
            integrality=["binary"],
            bounds=[{"lower": 0.5, "upper": 1.0}],
        )
    )
    lowers, uppers = validate_mip_request(request)
    assert lowers == [0.5]
    assert uppers == [1.0]


def test_binaria_con_cotas_vacias_se_rechaza() -> None:
    request = MIPRequest.model_validate(
        _payload(
            objective={"coefficients": [1.0]},
            integrality=["binary"],
            bounds=[{"lower": 2.0, "upper": 3.0}],
        )
    )
    with pytest.raises(ModelValidationError):
        validate_mip_request(request)


def test_binaria_con_lower_negativo_infinito_tambien_intersecta() -> None:
    request = MIPRequest.model_validate(
        _payload(
            objective={"coefficients": [1.0]},
            integrality=["binary"],
            bounds=[{"lower": None, "upper": None}],
        )
    )
    lowers, uppers = validate_mip_request(request)
    assert lowers == [0.0]
    assert uppers == [1.0]
