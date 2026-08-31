# Clustering API

Servicio de clustering genérico de Astaroth (familia de algoritmos de
agrupamiento): entrena, asigna puntos y expone métricas. Sigue el mismo
patrón que `XGBoost-api` (FastAPI + artefactos en `saved_models/`).

## Algoritmos soportados

| `algorithm` | Implementación |
|---|---|
| `kmeans` | `sklearn.cluster.KMeans` (Lloyd, `n_init=10`) |
| `minibatch` | `sklearn.cluster.MiniBatchKMeans` (para datasets grandes) |
| `gmm` | `sklearn.mixture.GaussianMixture` (clusters elípticos, pertenencia suave) |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio |
| POST | `/fit` | Entrena y guarda un modelo |
| POST | `/assign` | Asigna puntos a un modelo entrenado |
| GET | `/models` | Lista de modelos |
| GET | `/models/{name}` | Metadata del modelo |
| DELETE | `/models/{name}` | Elimina un modelo |
| GET | `/metrics/{name}` | Métricas del modelo |
| DELETE | `/admin/clear_all_models` | Borra todo (requiere `X-Admin-Key`) |

## Ejemplo

```bash
# Entrenar
curl -X POST http://localhost:8000/fit \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "seg_v1",
    "algorithm": "kmeans",
    "k": 5,
    "points": [[1.0, 2.0], [1.1, 2.1], [10.0, 20.0], [10.5, 20.5]]
  }'

# Asignar puntos nuevos
curl -X POST http://localhost:8000/assign \
  -H "Content-Type: application/json" \
  -d '{"model_name": "seg_v1", "points": [[1.2, 2.0]]}'
```

## Diseño

- El servicio es **agnóstico de la BD**: recibe los puntos por la API.
  Quien lee de Postgres (la réplica `pos.*`) es el pipeline del ecommerce
  (p. ej. la vista `analytics.vw_rfm_clientes` → puntos → esta API).
- Persistencia por modelo en `saved_models/{name}/`:
  `model.joblib` (pipeline scaler+clusterer), `centroids.json`,
  `metadata.json` (métricas y parámetros).
- La silueta se calcula sobre una muestra de máx. 10.000 puntos (es O(n²)).
- Los centroides se guardan en el **espacio original** (escala inversa).

## Notas de operación

- `MODELS_DIR` (default `saved_models`) y `ADMIN_KEY` se configuran por
  variables de entorno o `.env`.
- Para datasets grandes, preferir `minibatch`; los puntos viajan como JSON,
  así que el cuello de botella para 100K+ filas es el transporte — en ese
  caso conviene llamar `/fit` por lotes o exponer una variante que lea de
  Postgres (trabajo futuro).
