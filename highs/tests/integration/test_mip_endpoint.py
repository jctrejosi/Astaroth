"""Integración HTTP del endpoint MIP: knapsack, integralidad y límites."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _knapsack_payload() -> dict:
    return json.loads((EXAMPLES_DIR / "mip_knapsack.json").read_text(encoding="utf-8"))


def test_knapsack_devuelve_objetivo_220_y_estado_optimo(client: TestClient) -> None:
    response = client.post("/v1/mip/solve", json=_knapsack_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"
    assert abs(body["objective_value"] - 220.0) <= 1e-6

    x = body["variables"]
    assert x is not None
    assert abs(x[0] - 0.0) <= 1e-6
    assert abs(x[1] - 1.0) <= 1e-6
    assert abs(x[2] - 1.0) <= 1e-6


def test_binarias_toman_valores_0_o_1(client: TestClient) -> None:
    response = client.post("/v1/mip/solve", json=_knapsack_payload())
    x = response.json()["variables"]
    assert x is not None
    for value in x:
        assert abs(value - round(value)) <= 1e-6
        assert 0.0 - 1e-6 <= value <= 1.0 + 1e-6


def test_variables_enteras_respetan_integralidad(client: TestClient) -> None:
    payload = {
        "objective": {"coefficients": [1.0]},
        "constraints": [{"coefficients": [1.0], "sense": ">=", "rhs": 2.3}],
        "integrality": ["integer"],
    }
    response = client.post("/v1/mip/solve", json=payload)
    body = response.json()
    assert body["status"] == "optimal"
    x = body["variables"]
    assert x is not None
    assert abs(x[0] - 3.0) <= 1e-6


def test_limite_de_tiempo_no_se_presenta_como_optimo_si_no_se_probo(client: TestClient) -> None:
    payload = _knapsack_payload()
    payload["options"] = {"time_limit": 0}
    response = client.post("/v1/mip/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"time_limit", "optimal", "iteration_limit", "solution_limit"}
    if body["status"] != "optimal":
        assert body["message"] is not None


def test_metadata_de_mip_es_coherente(client: TestClient) -> None:
    response = client.post("/v1/mip/solve", json=_knapsack_payload())
    metadata = response.json()["metadata"]
    nodes = metadata["nodes_explored"]
    gap = metadata["gap"]
    # Nodos puede ser 0 (resuelto en presolve); si existe, nunca negativo.
    assert nodes is None or nodes >= 0
    assert gap is None or gap >= 0
    assert metadata["solver_used"] == "mip"
    assert metadata["engine_version"]
