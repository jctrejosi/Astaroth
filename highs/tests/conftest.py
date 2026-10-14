"""Fixtures compartidas de la suite."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from highs_api.config import settings
from highs_api.main import create_app

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Cliente HTTP de la aplicación real (sin mocks del motor)."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def quiet_client() -> Iterator[TestClient]:
    """Cliente que no re-lanza excepciones no controladas, para probar el 500."""
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def limited_body_limit(monkeypatch: pytest.MonkeyPatch) -> int:
    """Reduce el límite de tamaño de request para probar el 413 sin payloads enormes."""
    limit = 512
    monkeypatch.setattr(settings, "max_request_bytes", limit)
    return limit
