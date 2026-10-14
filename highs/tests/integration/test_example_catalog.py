"""Catálogo de ejemplos: cada problema se resuelve end-to-end contra la API.

Los óptimos esperados están calculados a mano sobre datasets diminutos; la
suite falla si el motor o la conversión dejan de reproducirlos.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _load(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES_DIR / name).read_text(encoding="utf-8"))


def _solve(client: TestClient, name: str, path: str) -> dict[str, Any]:
    response = client.post(path, json=_load(name))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "optimal", body
    return body


@pytest.mark.parametrize(
    ("example", "path", "expected_objective"),
    [
        ("lp_transport.json", "/v1/lp/solve", 500.0),
        ("lp_diet.json", "/v1/lp/solve", 10.0),
        ("lp_production_max.json", "/v1/lp/solve", 2600.0),
        ("mip_assignment.json", "/v1/mip/solve", 13.0),
        ("mip_facility.json", "/v1/mip/solve", 240.0),
    ],
)
def test_ejemplo_alcanza_el_optimo_conocido(
    client: TestClient, example: str, path: str, expected_objective: float
) -> None:
    body = _solve(client, example, path)
    assert body["objective_value"] is not None
    assert abs(body["objective_value"] - expected_objective) <= 1e-6


def test_transporte_conserva_oferta_y_demanda(client: TestClient) -> None:
    body = _solve(client, "lp_transport.json", "/v1/lp/solve")
    x = np.asarray(body["variables"])
    assert abs(x[0] + x[1] + x[2] - 30.0) <= 1e-6  # planta 1
    assert abs(x[3] + x[4] + x[5] - 40.0) <= 1e-6  # planta 2
    assert abs(x[0] + x[3] - 20.0) <= 1e-6  # bodega 1
    assert abs(x[1] + x[4] - 25.0) <= 1e-6  # bodega 2
    assert abs(x[2] + x[5] - 25.0) <= 1e-6  # bodega 3
    assert (x >= -1e-6).all()


def test_dieta_cumple_requerimientos_nutricionales(client: TestClient) -> None:
    body = _solve(client, "lp_diet.json", "/v1/lp/solve")
    x = np.asarray(body["variables"])
    assert 2 * x[0] + x[1] >= 10 - 1e-6
    assert x[0] + 3 * x[1] >= 15 - 1e-6
    assert (x >= -1e-6).all()


def test_produccion_maximiza_respetando_capacidades(client: TestClient) -> None:
    body = _solve(client, "lp_production_max.json", "/v1/lp/solve")
    x = np.asarray(body["variables"])
    assert 2 * x[0] + x[1] <= 100 + 1e-6
    assert x[0] + x[1] <= 80 + 1e-6
    assert -1e-6 <= x[0] <= 40 + 1e-6
    assert x[1] >= -1e-6
    assert abs(40 * x[0] + 30 * x[1] - body["objective_value"]) <= 1e-6


def test_asignacion_es_una_permutacion_binaria(client: TestClient) -> None:
    body = _solve(client, "mip_assignment.json", "/v1/mip/solve")
    x = np.asarray(body["variables"]).reshape(4, 4)
    assert (np.abs(x - np.round(x)) <= 1e-6).all()
    assert np.allclose(x.sum(axis=0), 1.0, atol=1e-6)  # cada tarea una vez
    assert np.allclose(x.sum(axis=1), 1.0, atol=1e-6)  # cada recurso una tarea


def test_localizacion_respeta_enlaces_big_m(client: TestClient) -> None:
    body = _solve(client, "mip_facility.json", "/v1/mip/solve")
    y1, y2, x11, x12, x13, x21, x22, x23 = body["variables"]
    # Con los costos del ejemplo solo conviene abrir la bodega 2.
    assert abs(y2 - 1.0) <= 1e-6
    assert abs(y1 - 0.0) <= 1e-6
    demands = (10.0, 10.0, 10.0)
    for shipping, demand, open_y in (
        (x11, demands[0], y1),
        (x12, demands[1], y1),
        (x13, demands[2], y1),
        (x21, demands[0], y2),
        (x22, demands[1], y2),
        (x23, demands[2], y2),
    ):
        assert shipping >= -1e-6
        assert shipping <= demand * open_y + 1e-6  # enlace big-M
    assert abs(x21 + x11 - demands[0]) <= 1e-6
    assert abs(x22 + x12 - demands[1]) <= 1e-6
    assert abs(x23 + x13 - demands[2]) <= 1e-6


def test_ridge_qp_reproduce_la_solucion_analitica(client: TestClient) -> None:
    payload = _load("qp_ridge.json")
    q = np.asarray(payload["Q"], dtype=float)
    c = np.asarray(payload["objective"]["coefficients"], dtype=float)

    # El óptimo de 0.5·xᵀQx + cᵀx con Q definida positiva resuelve Qx = −c.
    x_expected = np.linalg.solve(q, -c)

    response = client.post("/v1/qp/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"

    x = np.asarray(body["variables"])
    assert np.allclose(x, x_expected, atol=1e-6)
    expected_objective = 0.5 * x @ q @ x + c @ x
    assert abs(body["objective_value"] - expected_objective) <= 1e-6
