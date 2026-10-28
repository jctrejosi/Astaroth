# 12 — Rust y solucionador (interconexión con HiGHS)

## Stack del servidor

| Componente | Tecnología | Motivo |
|---|---|---|
| API HTTP | [Axum](https://github.com/tokio-rs/axum) | Rutas, solicitudes y respuestas JSON |
| Ejecución asíncrona | [Tokio](https://tokio.rs) | Runtime del servidor |
| Serialización | `serde` + `serde_json` | Convertir modelos a JSON |
| Errores | `thiserror` | Errores tipados internos |
| Observabilidad | `tracing` | Logs y diagnóstico |
| Algoritmos | Rust propio (inicial) | Control sobre las reglas de asignación |
| Optimización matemática | `good_lp` o solver externo (HiGHS) | Modelos con restricciones más complejas |

Axum integra HTTP + JSON con el ecosistema de Tokio y Tower.

## Estrategia de optimización

1. **Por defecto**: heurística propia en Rust (asignación greedy + búsqueda local).
2. **Cuando hace falta MILP / optimalidad**: delegar a **HiGHS**, usando el
   servicio existente en `Astaroth/highs` (FastAPI sobre `highspy`).

`good_lp` puede modelar MILP en Rust y enlazar con HiGHS como *backend* en proceso.
La decisión aquí es **apuntar al servicio HTTP `highs`** para no duplicar el motor
ni acoplar la librería C de HiGHS al binario de Rust.

## Servicio `highs` (existente)

Endpoints relevantes:

| Método y ruta | Uso |
|---|---|
| `GET /health` | Liveness (sin autenticación) |
| `GET /v1/capabilities` | Límites y versión del motor |
| `POST /v1/lp/solve` | LP (variables continuas) |
| `POST /v1/mip/solve` | MIP (con `integrality`) |
| `POST /v1/qp/solve` | QP convexo |

### Autenticación

Salvo `/health`, exige una de las claves de `API_KEYS`, enviada como
`X-API-Key` o `Authorization: Bearer <clave>`. Configuración del balanceador:

- `HIGHS_URL` (p. ej. `http://127.0.0.1:8015`)
- `HIGHS_API_KEY`

### Forma de la petición MIP

```json
{
  "objective": { "sense": "minimize", "coefficients": [0, 0, 1] },
  "constraints": [
    { "coefficients": [1, 1, 0], "sense": "=", "rhs": 1 }
  ],
  "bounds": null,
  "integrality": ["binary", "binary", "continuous"],
  "options": { "time_limit": 5, "mip_rel_gap": 0.01 }
}
```

Campos:

- `objective.sense`: `minimize` | `maximize`.
- `objective.coefficients`: longitud = número de variables.
- `constraints[].sense`: `"<="`, `">="` o `"="`.
- `bounds`: opcional, lista de `{ "lower", "upper" }`.
- `integrality`: `continuous` | `integer` | `binary` (obligatorio en MIP).
- `options`: `time_limit`, `threads`, `presolve`, `mip_rel_gap`, `random_seed`.

### Forma de la respuesta

```json
{
  "status": "optimal",
  "objective_value": 35.0,
  "variables": [1, 0, 35],
  "dual_values": null,
  "reduced_costs": null,
  "metadata": {
    "solve_time_ms": 12.3,
    "iterations": 10,
    "nodes_explored": 4,
    "gap": 0.0,
    "solver_used": "mip",
    "engine_version": "1.x.y"
  },
  "message": null
}
```

`status` puede ser: `optimal`, `infeasible`, `unbounded`, `time_limit`,
`iteration_limit`, `unknown`, entre otros.

## Mapeo del problema de asignación a MIP

Variables:

- $x_{ij} \in \{0,1\}$ por cada par (empleado, actividad) **elegible**.
- $M \ge 0$ (makespan), continua.

Objetivo:

- Minimizar $M$.

Restricciones:

1. Asignación única: $\sum_i x_{ij} = 1$ para cada actividad $j$.
2. Makespan: $r_i + \sum_j p_{ij} x_{ij} \le M$ para cada empleado $i$.
3. Capacidad (si se exige terminar en el horizonte):
   $r_i + \sum_j p_{ij} x_{ij} \le C_i(H)$.
4. Habilidades: solo se generan variables $x_{ij}$ para pares elegibles; el resto
   no existe (o se fija a 0).

Restricciones blandas (plazos, prioridades) pueden entrar como términos en el
objetivo o como variables de holgura penalizadas.

## Mapeo de estados HiGHS → balanceador

| HiGHS `status` | Balanceador `status` |
|---|---|
| `optimal` | `FEASIBLE` |
| `infeasible` | `CAPACITY_SHORTAGE` (o `UNASSIGNABLE` si la causa es elegibilidad) |
| `time_limit` / `iteration_limit` | `UNKNOWN` (no se pudo probar factibilidad) |
| `unbounded` | error / estado inválido del modelo |

> `infeasible` ≠ `time_limit`: solo el primero demuestra imposibilidad matemática.

## Cuándo usar HiGHS

- Cuando la heurística no demuestra optimalidad y se requiere una cota.
- Cuando aparecen restricciones combinadas (habilidades + plazos + secuencias)
  difíciles para la búsqueda local.
- Configurar un umbral (tamaño de instancia, tiempo disponible) para elegir
  heurística vs. MIP.

## Plan de interconexión

1. Definir un *trait* `Solver` en Rust con dos implementaciones:
   `HeuristicSolver` (propio) y `HighsHttpSolver` (cliente HTTP de `highs`).
2. Construir el modelo MIP en un módulo `milp` (independiente del solver).
3. `HighsHttpSolver` serializa el modelo al contrato `POST /v1/mip/solve` con
   `serde`, envía `X-API-Key` y deserializa `SolveResponse`.
4. Traducir `SolveResponse.status` → `status` del balanceador.
5. Incluir `solver.method` y `optimality_proven` en la respuesta `POST /v1/plan`.
