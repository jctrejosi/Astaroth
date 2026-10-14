"""E2E de la canasta familiar: del JSON de referencia a la respuesta HTTP.

El dataset es deliberadamente pequeño y determinista; un dataset comercial
real debe incorporar precios, stock, unidades y redondeos reales.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
COSTS = [12000.0, 18000.0, 4000.0, 3000.0, 5000.0, 4500.0]
_STOCK = [3, 4, 6, 5, 10, 4]


def _canasta_payload() -> dict:
    return json.loads((EXAMPLES_DIR / "mip_canasta.json").read_text(encoding="utf-8"))


def _assert_requerimientos(x: list[float]) -> None:
    assert x[0] + x[1] >= 5 - 1e-6
    assert x[2] + x[3] >= 4 - 1e-6
    assert x[4] >= 6 - 1e-6
    assert x[5] >= 3 - 1e-6
    for value in x:
        assert value >= -1e-6
        assert abs(value - round(value)) <= 1e-6


def test_canasta_referencia_objetivo_115500(client: TestClient) -> None:
    response = client.post("/v1/mip/solve", json=_canasta_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"
    assert abs(body["objective_value"] - 115500.0) <= 1e-6

    x = body["variables"]
    assert x is not None and len(x) == 6
    _assert_requerimientos(x)

    expected = sum(cost * value for cost, value in zip(COSTS, x, strict=True))
    assert abs(body["objective_value"] - expected) <= 1e-6


def test_canasta_con_stock_respeta_cotas_superiores(client: TestClient) -> None:
    """El stock se codifica como cotas superiores; si no se envía, no se valida."""
    payload = _canasta_payload()
    payload["bounds"] = [{"lower": 0, "upper": limit} for limit in _STOCK]

    response = client.post("/v1/mip/solve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "optimal"
    assert abs(body["objective_value"] - 127500.0) <= 1e-6

    x = body["variables"]
    assert x is not None
    _assert_requerimientos(x)
    for value, limit in zip(x, _STOCK, strict=True):
        assert value <= limit + 1e-6
