"""Integración HTTP del endpoint LP: estados, resultados y validaciones."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _mixing_payload() -> dict:
    return json.loads((EXAMPLES_DIR / "lp_mixing.json").read_text(encoding="utf-8"))


def test_lp_mezcla_satisface_restricciones_y_objetivo(client: TestClient) -> None:
    response = client.post("/v1/lp/solve", json=_mixing_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"

    x = body["variables"]
    assert x is not None and len(x) == 4
    assert abs(sum(x) - 100) <= 1e-6
    assert 0.1 * x[0] + 0.2 * x[1] + 0.3 * x[2] + 0.05 * x[3] >= 15 - 1e-6
    assert 0.5 * x[0] + 0.3 * x[1] + 0.2 * x[2] + 0.6 * x[3] <= 40 + 1e-6
    assert all(-1e-6 <= value <= 50 + 1e-6 for value in x)

    expected_objective = 10 * x[0] + 15 * x[1] + 20 * x[2] + 8 * x[3]
    assert abs(body["objective_value"] - expected_objective) <= 1e-6


def test_lp_devuelve_duales_y_costos_reducidos_validos(client: TestClient) -> None:
    response = client.post("/v1/lp/solve", json=_mixing_payload())
    body = response.json()

    assert body["dual_values"] is not None
    assert len(body["dual_values"]) == 3
    assert body["reduced_costs"] is not None
    assert len(body["reduced_costs"]) == 4


def test_lp_infactible_es_un_resultado_no_un_error(client: TestClient) -> None:
    payload = {
        "objective": {"coefficients": [1.0]},
        "constraints": [
            {"coefficients": [1.0], "sense": ">=", "rhs": 2.0},
            {"coefficients": [1.0], "sense": "<=", "rhs": 1.0},
        ],
    }
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "infeasible"
    assert body["variables"] is None
    assert body["objective_value"] is None
    assert body["message"] is not None


def test_lp_no_acotado(client: TestClient) -> None:
    payload = {"objective": {"coefficients": [-1.0]}}
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unbounded"
    # Un punto interno del solver no es una solución: no se reporta.
    assert body["variables"] is None
    assert body["objective_value"] is None
    assert body["dual_values"] is None


def test_payload_con_dimensiones_invalidas_422(client: TestClient) -> None:
    payload = {
        "objective": {"coefficients": [1.0, 2.0]},
        "constraints": [{"coefficients": [1.0], "sense": "<=", "rhs": 1.0}],
    }
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]


def test_time_limit_muy_pequeno_no_genera_500(client: TestClient) -> None:
    payload = _mixing_payload()
    payload["options"] = {"time_limit": 0}
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {
        "time_limit",
        "iteration_limit",
        "objective_bound",
        "optimal",
    }


def test_la_convencion_del_ejemplo_sigue_vigente(client: TestClient) -> None:
    """El JSON de `examples/` se mantiene alineado con el contrato vigente."""
    payload = _mixing_payload()
    assert payload["objective"]["sense"] == "minimize"
    assert len(payload["bounds"]) == len(payload["objective"]["coefficients"])
