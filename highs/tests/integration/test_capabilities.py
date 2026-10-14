"""Integración HTTP de /health y /v1/capabilities."""

from __future__ import annotations

from fastapi.testclient import TestClient

from highs_api import __version__
from highs_api.config import settings
from highs_api.core.converters import engine_version


def test_health_no_revela_detalles(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok"}


def test_capabilities_declara_tipos_y_limites(client: TestClient) -> None:
    response = client.get("/v1/capabilities")
    assert response.status_code == 200
    body = response.json()

    assert body["name"] == "highs"
    assert body["api_version"] == "v1"
    assert body["service_version"] == __version__
    assert body["engine"]["name"] == "HiGHS"
    assert body["engine"]["version"] == engine_version()

    assert body["problem_types"] == ["LP", "MIP", "QP"]
    assert body["constraint_types"] == ["<=", ">=", "="]

    assert body["variable_types_by_problem"]["LP"] == ["continuous"]
    assert body["variable_types_by_problem"]["MIP"] == ["continuous", "integer", "binary"]
    assert body["variable_types_by_problem"]["QP"] == ["continuous"]

    assert body["limits"]["max_variables"] == settings.max_variables
    assert body["limits"]["max_constraints"] == settings.max_constraints
    assert body["limits"]["max_matrix_elements"] == settings.max_matrix_elements
    assert body["limits"]["max_qp_variables"] == settings.max_qp_variables
    assert body["limits"]["max_request_bytes"] == settings.max_request_bytes
    assert body["limits"]["max_time_limit_seconds"] == settings.max_time_limit_seconds


def test_capabilities_declara_limitaciones_reales(client: TestClient) -> None:
    limitations = client.get("/v1/capabilities").json()["limitations"]
    joined = " ".join(limitations)
    assert "MIQP" in joined
    assert "MIQCP" in joined
    assert "NLP" in joined


def test_capabilities_no_publica_algoritmos_internos(client: TestClient) -> None:
    body = client.get("/v1/capabilities").json()
    assert "algorithms" not in body
    for options in body["options_by_problem"].values():
        assert "qpasm" not in options


def test_capabilities_no_publica_opciones_sin_significado(client: TestClient) -> None:
    body = client.get("/v1/capabilities").json()
    # `mip_rel_gap` no aplica al contrato QP y no debe figurar allí.
    assert "mip_rel_gap" not in body["options_by_problem"]["QP"]
    assert "qp_iteration_limit" not in body["options_by_problem"]["LP"]
