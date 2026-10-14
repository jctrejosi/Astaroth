# LP — Programación lineal

## Qué es y cuándo usarlo

Un LP optimiza una función lineal sujeta a restricciones lineales, con todas
las variables continuas. Úsalo para mezclas de producción, asignación de
recursos, flujos con costos lineales o planificación agregada. Si necesitas
cantidades enteras usa MIP; si el objetivo es cuadrático usa QP.

## Formulación

```
min/max  cᵀx
s.a.     aᵢᵀx ≤/≥/= bᵢ     (constraints)
         lower ≤ x ≤ upper  (bounds)
```

- `objective.coefficients` define el número de variables (`n ≥ 1`).
- `bounds` omitido ⇒ `[0, +∞)` por variable; en un elemento, `lower: null` es −∞
  y `upper: null` es +∞. `lower` omitido vale `0`.
- Los vectores son densos y todos los números deben ser finitos.

## Request

```json
POST /v1/lp/solve
{
  "objective": { "sense": "minimize", "coefficients": [10, 15, 20, 8] },
  "constraints": [
    { "coefficients": [1, 1, 1, 1], "sense": "=", "rhs": 100 },
    { "coefficients": [0.1, 0.2, 0.3, 0.05], "sense": ">=", "rhs": 15 },
    { "coefficients": [0.5, 0.3, 0.2, 0.6], "sense": "<=", "rhs": 40 }
  ],
  "bounds": [
    { "lower": 0, "upper": 50 },
    { "lower": 0, "upper": 50 },
    { "lower": 0, "upper": 50 },
    { "lower": 0, "upper": 50 }
  ],
  "options": { "solver": "choose", "presolve": "choose", "time_limit": 30 }
}
```

## Response

Esquema común (ver [architecture.md](architecture.md)). En un LP óptimo suelen
venir `dual_values` (uno por restricción) y `reduced_costs` (uno por variable),
solo si el motor los marca válidos. `nodes_explored` y `gap` son `null`; las
iteraciones corresponden a simplex/IPM según lo reportado.

## Opciones permitidas

| Opción | Valores | Nota |
|---|---|---|
| `solver` | `simplex`, `ipm`, `choose` | `choose` deja decidir al motor. |
| `presolve` | `on`, `off`, `choose` | Por defecto `choose`. |
| `time_limit` | número ≥ 0 o `null` | Segundos; `null` usa el default del servicio (`HIGHS_DEFAULT_TIME_LIMIT`). |
| `threads` | entero ≥ 0 o `null` | `0`/omitido ⇒ máximo configurado del servicio. |

Las opciones no aplicables a LP se rechazan como error de validación (422);
no se ignoran silenciosamente.

## Ejemplo ejecutable

```bash
curl -X POST http://127.0.0.1:8000/v1/lp/solve \
  -H "Content-Type: application/json" --data-binary @examples/lp_mixing.json
```

Respuesta resumida (valores redondeados del dataset de referencia; los tiempos
varían por máquina):

```json
{
  "status": "optimal",
  "objective_value": 1250.0,
  "variables": [50.0, 50.0, 0.0, 0.0],
  "dual_values": [5.0, 50.0, 0.0],
  "reduced_costs": [0.0, 0.0, 0.0, 0.5],
  "metadata": { "solve_time_ms": 0.9, "iterations": 2, "solver_used": "auto" },
  "message": null
}
```

Los valores exactos pueden variar entre versiones del motor; el test de
integración valida factibilidad y coherencia del objetivo recalculado, no un
vector fijo.

## Resultados no óptimos y límites

- `infeasible` / `unbounded` / `unbounded_or_infeasible`: el modelo no tiene
  solución o no está acotado; llegan con HTTP 200 y campos de solución `null`.
- `time_limit` (o límite equivalente): el objetivo y las variables pueden venir
  si HiGHS dispone de una solución válida; `message` lo indica explícitamente.
  No se afirma optimalidad sin certificado.
- LP enteramente resuelto por presolve puede reportar `iterations: 0`.

## Limitaciones conocidas (versión fijada, `highspy==1.15.1`)

- No se exponen otras opciones internas del motor (p. ej. selección de
  crossover o PDLP); el contrato público es deliberadamente reducido.
- El contrato inicial es denso: usa `/v1/capabilities` para ver los límites de
  dimensiones y bytes vigentes.
