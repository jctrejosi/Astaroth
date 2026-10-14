# highs — motor de optimización LP/MIP/QP

Servicio REST autocontenido que resuelve problemas de optimización con
[HiGHS](https://ergo-code.github.io/HiGHS/) a través de `highspy`. Cada request
incluye el modelo completo; la API no conserva estado entre llamadas.

## Problemas soportados

| Tipo | Endpoint | Variables | Objetivo |
|---|---|---|---|
| **LP** | `POST /v1/lp/solve` | continuas | lineal |
| **MIP** | `POST /v1/mip/solve` | continuas, enteras y binarias | lineal |
| **QP** | `POST /v1/qp/solve` | continuas | cuadrático convexo: `min 0.5·xᵀQx + cᵀx` |

Los estados de la resolución (`optimal`, `infeasible`, `unbounded`,
`time_limit`, …) son resultados válidos con HTTP 200; los errores de contrato
usan un esquema JSON único (ver [docs/architecture.md](docs/architecture.md)).

## Limitaciones de la versión 1

- No MIQP, MIQCP ni NLP; sin restricciones cuadráticas.
- QP solo de **minimización convexa** con `Q` simétrica y positiva semidefinida.
- Sin persistencia de modelos, jobs asíncronos ni resolución por lotes.
- Entrada densa: los límites de tamaño están en `/v1/capabilities`.
- Sin autenticación propia (ver *Seguridad y despliegue*).

## Endpoints

| Método | Ruta | Propósito |
|---|---|---|
| `GET` | `/health` | Liveness del proceso HTTP. |
| `GET` | `/v1/capabilities` | Tipos soportados, límites y limitaciones vigentes. |
| `POST` | `/v1/lp/solve` | Resolver un LP. |
| `POST` | `/v1/mip/solve` | Resolver un MIP. |
| `POST` | `/v1/qp/solve` | Resolver un QP convexo. |
| `GET` | `/docs`, `/redoc` | Documentación interactiva (OpenAPI). |

## Versiones

- Desarrollo local en Python 3.12; las imágenes Docker (la propia de `highs/` y
  la del monorepo Astaroth) usan **Python 3.11**, la misma versión menor que el
  resto del monorepo. El lockfile es compatible con 3.11+.
- `highspy==1.15.1` (versión fijada y probada; ver `requirements.lock`).
- FastAPI + Pydantic v2; uvicorn; NumPy para validar la matriz `Q`.

## Instalación y ejecución local

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn highs_api.main:app --reload --host 127.0.0.1 --port 8000
```

Configuración por entorno con prefijo `HIGHS_` (ver `.env.example`). Los
límites efectivos se publican en `/v1/capabilities`.

## Calidad

```bash
pytest -v
pytest --cov=highs_api --cov-report=term-missing --cov-fail-under=85
ruff check src tests
ruff format --check src tests
mypy src/highs_api
```

En Windows, sustituir `pytest`/`ruff`/`mypy` por `.venv\Scripts\python -m …`.
La cobertura medida actual es 95%; los benchmarks viven en `benchmarks/`.

## Ejemplos

```bash
curl http://127.0.0.1:8000/v1/capabilities
curl -X POST http://127.0.0.1:8000/v1/lp/solve \
  -H "Content-Type: application/json" --data-binary @examples/lp_mixing.json
curl -X POST http://127.0.0.1:8000/v1/mip/solve \
  -H "Content-Type: application/json" --data-binary @examples/mip_knapsack.json
curl -X POST http://127.0.0.1:8000/v1/qp/solve \
  -H "Content-Type: application/json" --data-binary @examples/qp_markowitz.json
```

Respuesta común (los campos no aplicables van en `null`):

```json
{
  "status": "optimal",
  "objective_value": 10.0,
  "variables": [2.0, 2.0],
  "dual_values": [2.0],
  "reduced_costs": [0.0, 0.0],
  "metadata": {
    "solve_time_ms": 1.25,
    "iterations": 3,
    "nodes_explored": null,
    "gap": null,
    "solver_used": "simplex",
    "engine_version": "1.15.1"
  },
  "message": null
}
```

## Docker

```bash
docker compose up --build     # publica 127.0.0.1:8000
docker compose down
```

La imagen instala `requirements.lock` y el paquete sin dependencias de
desarrollo. El contenedor incluye healthcheck sobre `/health`. Tamaño medido
con `docker images`: **342 MB** (objetivo práctico < 500 MB).

## Seguridad y despliegue

Esta API resuelve modelos proporcionados por el cliente y puede consumir CPU y
memoria de forma intensiva: **no debe exponerse a Internet sin autenticación y
controles de recursos** (firewall, red privada o reverse proxy). El puerto se
publica solo en localhost por defecto. Configurar además límites de memoria y
CPU del contenedor, y un timeout en el proxy independiente del `time_limit` del
solver.

## Documentación

- [docs/architecture.md](docs/architecture.md) — capas, ciclo de un request, estados y límites.
- [docs/lp.md](docs/lp.md), [docs/mip.md](docs/mip.md), [docs/qp.md](docs/qp.md) — guías por tipo de problema.
- [docs/canasta.md](docs/canasta.md) — caso de negocio: canasta familiar desde datos de PostgreSQL.
- [benchmarks/results.md](benchmarks/results.md) — valores medidos con hardware y versión registrados.
