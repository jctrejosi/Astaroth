"""Validaciones estructurales del contrato LP."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from highs_api.models.lp import LPRequest


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "objective": {"sense": "minimize", "coefficients": [1.0, 2.0]},
        "constraints": [{"coefficients": [1.0, 1.0], "sense": ">=", "rhs": 1.0}],
    }
    base.update(overrides)
    return base


def test_rechaza_bounds_de_longitud_incorrecta() -> None:
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(bounds=[{"lower": 0.0}]))


def test_rechaza_restricciones_con_vectores_de_longitud_incorrecta() -> None:
    with pytest.raises(ValidationError):
        LPRequest.model_validate(
            _payload(constraints=[{"coefficients": [1.0], "sense": "<=", "rhs": 2.0}])
        )


def test_rechaza_coeficientes_no_finitos() -> None:
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(objective={"coefficients": [float("nan")]}))
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(objective={"coefficients": [1.0, float("inf")]}))
    with pytest.raises(ValidationError):
        LPRequest.model_validate(
            _payload(
                constraints=[{"coefficients": [1.0, -float("inf")], "sense": "<=", "rhs": 1.0}]
            )
        )


def test_rechaza_cotas_contradictorias() -> None:
    with pytest.raises(ValidationError):
        LPRequest.model_validate(
            _payload(bounds=[{"lower": 5.0, "upper": 3.0}, {"lower": 0.0, "upper": 10.0}])
        )


def test_no_se_coercionan_strings_a_numeros() -> None:
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(objective={"coefficients": ["2"]}))


def test_rechaza_campos_extra() -> None:
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(Q=[[1.0, 0.0], [0.0, 1.0]]))
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(options={"mip_rel_gap": 0.01}))


def test_valida_opciones_lp() -> None:
    request = LPRequest.model_validate(_payload(options={"solver": "ipm", "time_limit": 5}))
    assert request.options.solver == "ipm"
    assert request.options.time_limit == 5.0
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(options={"solver": "gurobi"}))
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(options={"opcion_desconocida": 1}))
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(options={"time_limit": -1}))
    with pytest.raises(ValidationError):
        LPRequest.model_validate(_payload(options={"threads": -2}))


def test_cotas_por_defecto() -> None:
    request = LPRequest.model_validate(_payload())
    assert request.bounds is None

    request = LPRequest.model_validate(_payload(bounds=[{}, {}]))
    assert request.bounds is not None
    assert request.bounds[0].lower == 0.0
    assert request.bounds[0].upper is None

    request = LPRequest.model_validate(_payload(bounds=[{"lower": None}, {"upper": 5.0}]))
    assert request.bounds is not None
    assert request.bounds[0].lower is None
    assert request.bounds[1].upper == 5.0


def test_constraints_vacio_es_valido() -> None:
    request = LPRequest.model_validate(_payload(constraints=[]))
    assert request.constraints == []
