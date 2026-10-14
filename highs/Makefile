# Comandos de desarrollo del motor `highs`.
# En Windows, usar los equivalentes de `.venv/Scripts/` (ver README).

PYTHON ?= python
VENV ?= .venv
BIN := $(VENV)/bin

.PHONY: install dev test cov lint format typecheck check docker-build docker-up docker-down clean

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -e ".[dev]"

dev:
	$(BIN)/uvicorn highs_api.main:app --reload --host 127.0.0.1 --port 8000

test:
	$(BIN)/pytest -v

cov:
	$(BIN)/pytest --cov=highs_api --cov-report=term-missing --cov-fail-under=85

lint:
	$(BIN)/ruff check src tests
	$(BIN)/ruff format --check src tests

format:
	$(BIN)/ruff format src tests

typecheck:
	$(BIN)/mypy src/highs_api

check: lint typecheck test

docker-build:
	docker build -t highs-api .

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
