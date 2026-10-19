# Astaroth

Plataforma de **algoritmos de ML** como servicios (FastAPI), cada uno con su
propia imagen, artefactos y README. Consumida por los pipelines del ecommerce
de Mercaldas (plataforma de datos → estos servicios → campañas).

## Servicios

| Servicio | Puerto | Qué hace |
|---|---|---|
| `clustering-api` | 8010 | Clustering (kmeans/minibatch/gmm): fit, assign, métricas |
| `XGBoost-api` | 8011 | XGBoost: regresión temporal + **propensión de compra** (SHAP) |
| `uplift-api` | 8012 | Uplift con econml (DR-learner, causal forest, X/T): Qini/AUUC |
| `transformerApi` | 8013 | iTransformer: pronóstico de series temporales (PyTorch) |
| `causalTransformer-api` | 8014 | Causal Transformer (ICML'22): contrafactuales temporales (PyTorch) |
| `highs` | 8015 | Optimización: LP, MIP y QP convexo sobre HiGHS (`/v1/{lp,mip,qp}/solve`) |
| `core/` | — | Librería compartida (lector `.ADT`, limpieza, RFM) — no es un servicio |

> **`linear-regression` NO está en el despliegue**: es un proyecto de curso
> (Flask + gpt4all/ollama + frontend + compose propio), no una API lista para
> producción. Si algún día se quiere exponer, se integra aparte.

## Local: `node dev.js`

Un solo lanzador con **selección por parámetros** (segundo plano, logs en
`logs/*.log`):

```bash
node dev.js                        # los 6 servicios
node dev.js --analytics            # solo lo que consume el ecommerce/analytics:
                                   #   clustering (8010) + xgboost (8011) + uplift (8012)
node dev.js --clustering --uplift  # servicios concretos (combinables)
node dev.js --transformer --causal # los pesados (PyTorch)
node dev.js --highs                # optimización LP/MIP/QP (8015)
node dev.js --prod                 # producción (sin --reload)
node dev.js --stop [flags]         # detiene (todos, o solo los seleccionados)
node dev.js --help
```

Cada servicio usa su propio `.venv`
(si falta, el script te dice cómo crearlo:
`cd servicio && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`).
Los servicios PyTorch (`transformerApi`, `causalTransformer-api`) necesitan
RAM y tardan en importar torch; en local conviene levantarlos solo si los vas
a usar (o usar `--analytics` para evitarlos).

Docs de cada API en `http://localhost:{puerto}/docs`.

## Despliegue en Render

Un solo servicio web (Docker) con Caddy ruteando por prefijo:

```
Astaroth/<dominio>/
├── /clustering/*   → clustering-api       :8010
├── /xgboost/*      → xgboost-api          :8011
├── /uplift/*       → uplift-api           :8012
├── /transformer/*  → transformerApi       :8013
├── /causal/*       → causalTransformer-api :8014
└── /highs/*        → highs (LP/MIP/QP)    :8015
```

1. Sube el repo a GitHub.
2. En Render → New Web Service → conéctalo.
3. **Runtime**: Docker · **Dockerfile**: `./Dockerfile` · **Root dir**: `Astaroth/`.
   (o usa `render.yaml` desde el dashboard: New → Blueprint)
4. Define `ADMIN_KEY` en las variables de entorno.
5. Health check: `/clustering/health`.

**⚠️ RAM**: el contenedor completo (con los 2 servicios PyTorch) necesita un
plan de **al menos 4 GB**. Con Starter (512 MB) solo funcionan los 3 servicios
ligeros; en ese caso quita los PyTorch del entrypoint o despliégalos como
servicios separados (cada uno tiene su Dockerfile).

Build local opcional:

```bash
docker build -t astaroth . && docker run --rm -p 10000:10000 -e PORT=10000 astaroth
# probar: curl localhost:10000/clustering/health
```

## Contenedor con puertos separados (`docker compose`)

Un solo contenedor, cada servicio en su propio puerto del host:

```bash
docker compose up --build
# clustering  → http://localhost:8010/docs
# xgboost     → http://localhost:8011/docs
# uplift      → http://localhost:8012/docs
# transformer → http://localhost:8013/docs   (PyTorch)
# causal      → http://localhost:8014/docs   (PyTorch)
# highs       → http://localhost:8015/docs   (LP/MIP/QP)
```

Comportamiento por variable de entorno (también en `docker-compose.yml` o un
`.env`):

- `ASTROTH_HOST` — host de escucha de los uvicorn (defecto `0.0.0.0`).
- `ASTROTH_FULL` — `1` (defecto) arranca los 6; `0` solo el trío ligero + highs.
- `ASTROTH_PROXY` — `1` arranca Caddy por prefijo en `$PORT`; `0` (defecto en
  compose) expone solo los puertos directos.
- `ADMIN_KEY` y `DATABASE_URL` — igual que en Render.
- `HIGHS_*` — límites del motor de optimización (ver `highs/.env.example`);
  los efectivos se publican en `GET /v1/capabilities`.

Los `uvicorn` escuchan en todas las interfaces, así que **todos** los puertos
(no solo los publicados) son alcanzables; para publicar solo algunos, edita la
sección `ports:` del compose.

## Seguridad de dependencias

Auditoría con `pip-audit` (OSV/PyPA) y actualización semanal con Dependabot
(`.github/dependabot.yml`). Estado actual, cambios aplicados y política de
actualización: [SECURITY.md](SECURITY.md).

```bash
python -m pip install pip-audit
python -m pip_audit -r highs/requirements.lock   # repetir por cada manifiesto
```

## Notas

- Los modelos guardados (`saved_models/`) están gitignored y viven en el
  volumen del servicio; para persistir artefactos entrenados en producción,
  montar un volumen o guardarlos en objeto de almacenamiento.
- `core/` se usa vía `PYTHONPATH=Astaroth` (ver `core/README.md` y
  `core/NOTAS_LEGADO.md`).
