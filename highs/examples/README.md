# Catálogo de ejemplos

Requests listos para `curl` contra el servicio (`--data-binary @examples/<archivo>`).
Cada uno cubre un tipo de problema distinto y tiene un óptimo determinista
verificado por la suite (`tests/integration/test_example_catalog.py` y
`tests/e2e/test_canasta.py`).

| Archivo | Endpoint | Tipo de problema | Óptimo esperado |
|---|---|---|---|
| `lp_mixing.json` | `/v1/lp/solve` | Mezcla de producción (LP min, igualdades y rangos) | verificado por propiedades |
| `lp_transport.json` | `/v1/lp/solve` | Transporte 2 plantas × 3 bodegas (oferta = demanda) | `500` |
| `lp_diet.json` | `/v1/lp/solve` | Dieta mínima (2 nutrientes, 2 alimentos) | `10` |
| `lp_production_max.json` | `/v1/lp/solve` | Producción **maximizando** utilidad con cotas | `2600` |
| `mip_knapsack.json` | `/v1/mip/solve` | Mochila 0/1 (3 binarias, maximizar) | `220` |
| `mip_canasta.json` | `/v1/mip/solve` | Canasta familiar (enteras, grupos de requerimiento) | `115500` |
| `mip_assignment.json` | `/v1/mip/solve` | Asignación 4×4 (16 binarias, una tarea por recurso) | `13` |
| `mip_facility.json` | `/v1/mip/solve` | Localización con costo fijo (big-M, binarias + continuas) | `240` |
| `qp_markowitz.json` | `/v1/qp/solve` | Cartera de mínima varianza (Q de covarianzas) | verificado por propiedades |
| `qp_ridge.json` | `/v1/qp/solve` | Regresión ridge `min ‖Ax−b‖² + λ‖x‖²` (variables libres) | solución analítica |

```bash
# con el servicio corriendo (node dev.js --highs  o  docker compose up)
curl -X POST http://localhost:8015/v1/lp/solve \
  -H "Content-Type: application/json" --data-binary @examples/lp_transport.json
```

Notas:

- Los óptimos de la tabla están calculados a mano y re-verificados por la suite;
  si HiGHS cambiara un valor, el test falla antes que la documentación.
- `qp_ridge.json` usa `bounds` con `lower: null`/`upper: null` (variables
  libres): es también un caso de contrato de cotas infinitas.
