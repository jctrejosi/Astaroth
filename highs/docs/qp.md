# QP — Programación cuadrática convexa

## Qué es y cuándo usarlo

Un QP minimiza una función cuadrática convexa sujeta a restricciones lineales:
carteras de mínima varianza, ajuste de curvas con regularización, control con
costos cuadráticos. La versión 1 acepta **solo minimización convexa**: `Q`
simétrica y positiva semidefinida (PSD).

## Formulación y convención

```
min  0.5·xᵀQx + cᵀx
s.a. aᵢᵀx ≤/≥/= bᵢ
     lower ≤ x ≤ upper
```

La convención `0.5` importa para interpretar `objective_value`: si se pasa una
matriz de covarianzas `Σ` directamente como `Q`, el valor reportado es
`0.5·xᵀΣx + cᵀx`. Los pesos óptimos no cambian al variar el factor, el número
reportado sí.

Validaciones (antes de tocar el motor, con respuesta 422):

1. `Q` cuadrada `n×n`, con `n = len(objective.coefficients)`.
2. Valores finitos; `Q` simétrica dentro de tolerancia `1e-9` relativa a su escala.
3. `Q` PSD dentro de tolerancia numérica (`eigvalsh`); `max_qp_variables` limita el tamaño.
4. `sense` debe ser `minimize`; `maximize` se rechaza en v1.

## Request

```json
POST /v1/qp/solve
{
  "objective": { "sense": "minimize", "coefficients": [0, 0, 0] },
  "Q": [
    [0.04, 0.01, 0.00],
    [0.01, 0.09, 0.02],
    [0.00, 0.02, 0.16]
  ],
  "constraints": [
    { "coefficients": [1, 1, 1], "sense": "=", "rhs": 1 },
    { "coefficients": [0.08, 0.12, 0.15], "sense": ">=", "rhs": 0.10 }
  ],
  "bounds": [
    { "lower": 0, "upper": 1 },
    { "lower": 0, "upper": 1 },
    { "lower": 0, "upper": 1 }
  ],
  "options": { "time_limit": 30, "solver": "qpasm" }
}
```

## Response

Esquema común. Para el QP resuelto, `metadata.iterations` corresponde a las
iteraciones del solver active-set (`qp_iteration_count`). `dual_values` y
`reduced_costs` se devuelven únicamente cuando HiGHS los marca como válidos
(con `qpasm` suelen serlo); si no, van en `null`. No se promete su existencia:
el cliente no debe depender de ellos.

## Opciones permitidas

| Opción | Valores | Nota |
|---|---|---|
| `solver` | `qpasm`, `choose` | `qpasm` es el solver active-set; `qp` **no** es una opción válida. |
| `presolve` | `on`, `off`, `choose` | Por defecto `choose`. |
| `time_limit` | número ≥ 0 o `null` | Segundos. |
| `threads` | entero ≥ 0 o `null` | `0`/omitido ⇒ máximo del servicio. |
| `qp_iteration_limit` | entero ≥ 0 o `null` | Límite no negativo de iteraciones del QP. |

`mip_rel_gap` y `random_seed` no forman parte del contrato QP: enviarlos
produce 422, no se ignoran en silencio.

## Ejemplo ejecutable (Markowitz)

```bash
curl -X POST http://127.0.0.1:8000/v1/qp/solve \
  -H "Content-Type: application/json" --data-binary @examples/qp_markowitz.json
```

Resultado del dataset de referencia (pesos redondeados):

```json
{
  "status": "optimal",
  "objective_value": 0.013981,
  "variables": [0.6218, 0.2159, 0.1623],
  "dual_values": [0.0233, 0.0466],
  "metadata": { "iterations": 4, "solver_used": "qpasm" },
  "message": null
}
```

Los pesos suman 1 y cumplen el rendimiento mínimo `0.08x₁+0.12x₂+0.15x₃ ≥ 0.10`.
El test de integración verifica factibilidad y la convención del objetivo
(`0.5·xᵀQx + cᵀx`), sin fijar un vector exacto de pesos.

## Resultados no óptimos y límites

- `time_limit`/`iteration_limit`: la solución puede venir si es válida; los
  campos van en `null` en caso contrario, con `message` explicativo.
- `infeasible` y `unbounded` (en la práctica, modelos mal planteados) llegan
  como resultado con HTTP 200, igual que en LP/MIP.

## Limitaciones conocidas

- Sin MIQP/MIQCP ni QP cóncavo (`maximize`), y sin restricciones cuadráticas.
- `max_qp_variables` (por defecto 500) acota el tamaño porque la validación
  PSD usa `eigvalsh` sobre la matriz densa.
- La versión de HiGHS está fijada; el soporte de QP y los nombres de opciones
  se validan contra `highspy==1.15.1`.
