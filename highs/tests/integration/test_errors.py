"""Contrato de errores HTTP: esquema común, 413, 422, 500 y límites."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from highs_api.core.exceptions import SolverExecutionError

_ERROR_SCHEMA_KEYS = {"code", "message", "details"}


def test_json_invalido_devuelve_422_con_esquema_comun(client: TestClient) -> None:
    response = client.post(
        "/v1/lp/solve",
        content=b"{esto no es json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    body = response.json()
    assert set(body["error"]) == _ERROR_SCHEMA_KEYS
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_validacion_semantica_devuelve_422(client: TestClient) -> None:
    payload = {
        "objective": {"coefficients": [1.0]},
        "bounds": [{"lower": 0.0}, {"lower": 0.0}],
    }
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]


def test_request_demasiado_grande_devuelve_413(client: TestClient, limited_body_limit: int) -> None:
    # El payload (JSON compacto en el wire) supera holgadamente el límite de 512 bytes.
    payload = {"objective": {"coefficients": [1.0] * 300}}
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 413
    body = response.json()
    assert set(body["error"]) == _ERROR_SCHEMA_KEYS
    assert body["error"]["code"] == "REQUEST_TOO_LARGE"


def test_fallo_inesperado_devuelve_500_generico_y_registra_interno(
    quiet_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import highs_api.api.lp_routes as lp_routes

    def _boom(request: object) -> None:
        raise RuntimeError("detalle interno que no debe salir")

    monkeypatch.setattr(lp_routes, "solve_lp", _boom)
    caplog.set_level(logging.ERROR)

    response = quiet_client.post("/v1/lp/solve", json={"objective": {"coefficients": [1.0]}})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "detalle interno" not in response.text
    assert "Traceback" not in response.text
    assert any(record.getMessage() == "unhandled_error" for record in caplog.records)


def test_fallo_controlado_del_solver_devuelve_solver_error(
    quiet_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import highs_api.api.lp_routes as lp_routes

    def _solver_failure(request: object) -> None:
        raise SolverExecutionError()

    monkeypatch.setattr(lp_routes, "solve_lp", _solver_failure)
    response = quiet_client.post("/v1/lp/solve", json={"objective": {"coefficients": [1.0]}})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "SOLVER_ERROR"
    assert body["error"]["message"]
    assert "Traceback" not in response.text


def test_infactible_no_se_convierte_en_error_http(client: TestClient) -> None:
    payload = {
        "objective": {"coefficients": [1.0]},
        "constraints": [
            {"coefficients": [1.0], "sense": ">=", "rhs": 2.0},
            {"coefficients": [1.0], "sense": "<=", "rhs": 1.0},
        ],
    }
    response = client.post("/v1/lp/solve", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "infeasible"
