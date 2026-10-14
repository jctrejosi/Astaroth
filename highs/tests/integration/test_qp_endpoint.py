"""Integración HTTP del endpoint QP: convexidad, Markowitz y validaciones."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _markowitz_payload() -> dict:
    return json.loads((EXAMPLES_DIR / "qp_markowitz.json").read_text(encoding="utf-8"))


def test_qp_psd_de_referencia_resuelve_optimo(client: TestClient) -> None:
    payload = {
        "objective": {"sense": "minimize", "coefficients": [-1.0, -2.0]},
        "Q": [[2.0, 0.0], [0.0, 4.0]],
        "bounds": [
            {"lower": 0, "upper": 2},
            {"lower": 0, "upper": 2},
        ],
    }
    response = client.post("/v1/qp/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"

    x = body["variables"]
    assert x is not None
    assert abs(x[0] - 0.5) <= 1e-5
    assert abs(x[1] - 0.5) <= 1e-5
    # Convención 0.5 * x'Qx + c'x
    assert abs(body["objective_value"] - (-0.75)) <= 1e-6


def test_markowitz_pesos_factibles_y_suma_1(client: TestClient) -> None:
    payload = _markowitz_payload()
    response = client.post("/v1/qp/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"

    x = body["variables"]
    assert x is not None
    assert abs(sum(x) - 1.0) <= 1e-6
    assert all(-1e-6 <= value <= 1.0 + 1e-6 for value in x)
    returns = 0.08 * x[0] + 0.12 * x[1] + 0.15 * x[2]
    assert returns >= 0.10 - 1e-6

    q = payload["Q"]
    expected = 0.5 * sum(x[i] * q[i][j] * x[j] for i in range(3) for j in range(3))
    assert abs(body["objective_value"] - expected) <= 1e-9


def test_duales_de_qp_solo_cuando_son_validos(client: TestClient) -> None:
    response = client.post("/v1/qp/solve", json=_markowitz_payload())
    body = response.json()
    # No se promete su existencia, pero si llegan deben ser coherentes.
    if body["dual_values"] is not None:
        assert len(body["dual_values"]) == 2
    if body["reduced_costs"] is not None:
        assert len(body["reduced_costs"]) == 3


def test_q_no_simetrica_devuelve_422_validacion(client: TestClient) -> None:
    payload = {
        "objective": {"sense": "minimize", "coefficients": [0.0, 0.0]},
        "Q": [[1.0, 2.0], [0.0, 1.0]],
    }
    response = client.post("/v1/qp/solve", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_q_no_psd_devuelve_422_validacion(client: TestClient) -> None:
    payload = {
        "objective": {"sense": "minimize", "coefficients": [0.0, 0.0]},
        "Q": [[1.0, 2.0], [2.0, 1.0]],
    }
    response = client.post("/v1/qp/solve", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_maximize_en_qp_devuelve_422(client: TestClient) -> None:
    payload = {
        "objective": {"sense": "maximize", "coefficients": [0.0]},
        "Q": [[1.0]],
    }
    response = client.post("/v1/qp/solve", json=payload)
    assert response.status_code == 422
