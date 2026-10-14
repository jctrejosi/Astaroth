# MIP — Programación entera mixta

## Qué es y cuándo usarlo

Un MIP es un LP con variables enteras o binarias: mochilas, canastas,
planificación de compras por unidades, asignaciones sí/no. Si todas las
variables pueden ser fraccionarias, usa LP.

## Formulación

```
min/max  cᵀx
s.a.     aᵢᵀx ≤/≥/= bᵢ
         lower ≤ x ≤ upper
         xⱼ ∈ ℤ  para j integer/binary
```

Reglas del dominio binario:

- Sin cotas, una binaria tiene dominio `[0, 1]`.
- Las cotas del cliente se intersectan con `[0, 1]`: `[0, 0.5]` solo puede
  tomar `0`; `[0.5, 1]` solo `1`.
- Si la intersección es vacía (p. ej. `[2, 3]`) el request se rechaza con 422;
  nunca se sobrescriben cotas en silencio.

## Request

```json
POST /v1/mip/solve
{
  "objective": { "sense": "maximize", "coefficients": [60, 100, 120] },
  "constraints": [ { "coefficients": [10, 20, 30], "sense": "<=", "rhs": 50 } ],
  "integrality": ["binary", "binary", "binary"],
  "options": { "time_limit": 30, "mip_rel_gap": 0 }
}
```

`integrality` es obligatoria y debe tener un tipo por variable
(`continuous`, `integer`, `binary`).

## Response

Esquema común. En MIP:

- `dual_values` y `reduced_costs` son `null` (HiGHS no los marca válidos).
- `metadata.nodes_explored` puede ser `0` (resuelto en presolve) y nunca es
  negativo; `metadata.gap` aparece cuando el motor lo reporta finito.
- `variables`/`objective_value` pueden venir aunque el estado sea un límite,
  siempre que exista un incumbente válido; el `status` y `message` distinguen
  claramente una solución factible de un óptimo probado.

## Opciones permitidas

| Opción | Valores | Nota |
|---|---|---|
| `presolve` | `on`, `off`, `choose` | Por defecto `choose`. |
| `time_limit` | número ≥ 0 o `null` | Segundos. |
| `threads` | entero ≥ 0 o `null` | `0`/omitido ⇒ máximo del servicio. |
| `mip_rel_gap` | número ≥ 0 o `null` | Gap relativo aceptado. |
| `random_seed` | entero ≥ 0 (≤ 2³¹−1) | Reproducibilidad del árbol. |

La opción `solver` **no** forma parte del contrato MIP: un cliente no debe
poder cambiar accidentalmente la semántica entera del problema.

## Ejemplo ejecutable

```bash
curl -X POST http://127.0.0.1:8000/v1/mip/solve \
  -H "Content-Type: application/json" --data-binary @examples/mip_knapsack.json
```

Devuelve `objective_value: 220` con la segunda y tercera variables
seleccionadas (dataset fijo del ejemplo).

La canasta familiar está desarrollada como caso de negocio en
[canasta.md](canasta.md): objetivo `115500` con el dataset de referencia.

## Resultados no óptimos y límites

- `time_limit`/`iteration_limit`/`solution_limit`: si hay incumbente válido se
  devuelve junto con `gap` (si el motor lo conoce) y un `message` que aclara
  que no se probó optimalidad.
- `infeasible`: puede ocurrir por demanda inalcanzable con el stock/cotas
  dadas; llega con HTTP 200.
- `infeasible`/`unbounded` y demás estados no portan solución: los campos van
  en `null`.

## Limitaciones conocidas

- Sin MIQP/MIQCP: no se aceptan variables enteras junto con matriz `Q`.
- No hay warm start ni callbacks públicos del árbol de búsqueda.
- La tolerancia de integralidad y el comportamiento del presolve son los del
  motor fijado (`highspy==1.15.1`).
