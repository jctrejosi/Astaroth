# 11 — Decisiones

## Decisiones tomadas

| Decisión | Elección |
|---|---|
| Arquitectura | Servicio **stateless** (sin base de datos propia ni estado operativo persistente) |
| Lenguaje | **Rust** (Axum + Tokio) |
| Serialización | `serde` / `serde_json` |
| Errores | `thiserror` |
| Observabilidad | `tracing` |
| Algoritmo inicial | Heurística propia en Rust (greedy + búsqueda local) |
| Optimización matemática | Delegar a **HiGHS** (servicio `Astaroth/highs`) vía `POST /v1/mip/solve` |
| API | `POST /v1/plan` (snapshot de entrada → plan + cambios + métricas) |

Detalles de la interconexión con HiGHS en
[`12-rust-y-solucionador.md`](12-rust-y-solucionador.md).

## Decisiones abiertas

- **Umbral heurística → HiGHS**: tamaño de instancia o tiempo máximo a partir del
  cual se usa MILP en lugar de la búsqueda local.
- **`good_lp` vs. HiGHS HTTP**: si en el futuro conviene modelar con `good_lp` en
  proceso (backend HiGHS embebido) o mantener siempre el servicio HTTP externo.
- **Parámetros operativos** (dependientes del contexto, no fijar arbitrarios):
  - $\alpha$ del EMA.
  - Umbral de mejora mínima para reasignar.
  - Coste de reasignación.
  - Tiempo mínimo entre reasignaciones.
  - Límite de cambios por ciclo.
  - Tiempo máximo del optimizador.
- **Contrato definitivo**: confirmar si `POST /v1/plan` devuelve siempre el plan
  completo + cambios (recomendado) y el esquema exacto de prioridades, plazos y
  dependencias.
- **`demand_forecaster`**: arrancar deshabilitado (sin datos) o con una fuente
  histórica.
- **Concurrencia en el cliente**: cómo detecta la aplicación que el estado cambió
  entre la lectura del snapshot y la aplicación de la respuesta.

## Contexto (fuente)

- `Astaroth/highs` expone LP/MIP/QP sobre `highspy` con autenticación `X-API-Key` /
  `Authorization: Bearer`. El balanceador lo consumirá como servicio HTTP.
