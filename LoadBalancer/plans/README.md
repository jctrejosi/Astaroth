# Balanceador dinámico de carga de trabajo

> Estado: **implementación completa del núcleo stateless (fase 2)**. Compila,
> pasa 26 tests y expone `POST /v1/plan`, `GET /health` y `GET /metrics`. Incluye
> dependencias, turnos, sobrecarga por empleado, arranque en frío, EMA y forecast.

Sistema planificador dinámico de actividades con capacidad limitada, estimación de
tiempos y detección de insuficiencia de recursos. Su objetivo **no** es repartir
tareas de forma uniforme, sino encontrar la mejor distribución posible, adaptarse
a los cambios operativos y detectar cuándo la demanda supera la capacidad
disponible.

## Reglas de partida

1. Cada actividad tiene una duración estimada que **depende del empleado** que la
   realiza.
2. Cada empleado tiene habilidades, velocidad de ejecución y capacidad máxima.
3. Una actividad **en ejecución no se interrumpe ni se reasigna**.
4. Las actividades **pendientes sí pueden reasignarse** cuando hay una mejora
   significativa.
5. El sistema considera tareas nuevas, avances reales, ausencias, cambios de turno
   y variaciones de duración.
6. El balanceador distingue entre una **mala distribución** y una **falta real de
   capacidad**.
7. El objetivo principal es **minimizar el tiempo de finalización de todo el
   trabajo** (makespan), respetando plazos y restricciones operativas.

## Arquitectura (decidida)

Servicio **stateless en Rust** (Axum + Tokio). No tiene base de datos propia ni
estado persistente: recibe una instantánea en `POST /v1/plan` y devuelve plan,
cambios, métricas y déficit. El estado operativo vive en la aplicación cliente.
Ver [`03-arquitectura-logica.md`](03-arquitectura-logica.md) y
[`12-rust-y-solucionador.md`](12-rust-y-solucionador.md).

## Código

Servicio en `../` (crate `load-balancer`). Compila con `cargo build` y pasa los
26 tests con `cargo test`. Contenedor: [`../Dockerfile`](../Dockerfile) (imagen
`load-balancer:local`, puerto 8016).

- `src/main.rs` — servidor Axum (`POST /v1/plan`, `GET /health`, `GET /metrics`),
  orquesta validación → solver → capacidad → respuesta.
- `src/model.rs` — modelos `serde` del contrato (request, respuesta, opciones,
  observaciones de duración e historial de llegadas).
- `src/domain.rs` — elegibilidad, duración por empleado (con fallback de media de
  equipo), capacidad efectiva por turnos y carga restante.
- `src/validator.rs` — validación de entrada (IDs, referencias, ciclos de
  dependencias).
- `src/solver.rs` — *trait* `Solver` + `HeuristicSolver` (asignación por lista que
  respeta dependencias + búsqueda local con preferencia suave por capacidad).
- `src/capacity.rs` — déficit agregado y por habilidad, sobrecarga por empleado,
  tareas inasignables y riesgo de plazo.
- `src/estimator.rs` — EMA para duraciones y proyección de demanda.
- `src/orchestrator.rs` — compone `PlanResponse` y resuelve el estado final.
- `src/milp.rs` — construcción del MIP para HiGHS.
- `src/highs.rs` — cliente HTTP de `Astaroth/highs`.
- `src/metrics.rs` — contador de solicitudes (formato Prometheus).
- `src/config.rs` — configuración por entorno (`LOAD_BALANCER_PORT`, `HIGHS_URL`,
  `HIGHS_API_KEY`).
- `src/error.rs` — errores tipados y respuestas HTTP.

### Capacidades implementadas

- **Dependencias**: la asignación por lista respeta el orden (una tarea solo se
  planifica cuando terminan sus dependencias) y calcula el makespan con tiempos
  de espera.
- **Turnos/calendario**: si un empleado define `shifts`, su capacidad efectiva se
  calcula a partir de los turnos acotados al horizonte; si no, se usa
  `available_minutes`.
- **Capacidad por empleado**: `enforce_capacity` hace que la heurística prefiera
  no sobrecargar; la sobrecarga se detecta aparte (`EMPLOYEE_OVERLOADED` →
  `CAPACITY_SHORTAGE`).
- **Arranque en frío**: un empleado con la habilidad pero sin estimación usa la
  media del equipo para esa tarea.
- **Aprendizaje (EMA)**: `duration_observations` + `ema_alpha` devuelven
  `updated_estimates` para que el cliente las persista.
- **Forecast de demanda**: `arrival_history` + `forecast_periods` devuelven
  `demand_forecast`.

### Fuera del alcance del servicio stateless

La API operativa completa del diseño (crear tareas, iniciar/finalizar, registrar
empleados, auditoría, versionado) es responsabilidad de la **aplicación cliente**,
que posee el estado. Este servicio solo calcula planes a partir de una instantánea.

### Ejecución local

```sh
export PATH="$HOME/.cargo/bin:$PATH"
LOAD_BALANCER_PORT=8016 cargo run
```

El puerto por defecto es **8016** (siguiente libre del rango 8010-8015 reservado
para los servicios ML de Astaroth). Configurable con `LOAD_BALANCER_PORT`.

```sh
curl -s http://127.0.0.1:8016/health
# ok

curl -s http://127.0.0.1:8016/metrics
# # HELP load_balancer_plan_requests_total ...
```

### Docker

```sh
docker build -t load-balancer:local -f LoadBalancer/Dockerfile LoadBalancer/
docker run --rm -p 8016:8016 load-balancer:local
```

También está integrado en el `docker-compose.yml` de Astaroth como servicio
`load-balancer` (publica en 8016 y llama a `highs` vía `http://astaroth:8015`).

## Objetivos del sistema

- **Asignación inteligente**: elegir al empleado más conveniente para cada
  actividad según carga, velocidad, habilidades y disponibilidad.
- **Rebalanceo dinámico**: recalcular las asignaciones pendientes cuando cambie el
  estado, sin interrumpir actividades en ejecución.
- **Control de capacidad**: determinar si los recursos pueden atender la demanda
  dentro del horizonte y los plazos requeridos.
- **Aprendizaje operativo**: comparar tiempos previstos con reales y actualizar
  las estimaciones.

## Índice de documentos

| Documento | Contenido |
|---|---|
| [`01-modelo-de-dominio.md`](01-modelo-de-dominio.md) | Empleado, actividad, plan de asignación, estados |
| [`02-modelo-matematico.md`](02-modelo-matematico.md) | Variables, carga proyectada, makespan, restricciones, objetivos |
| [`03-arquitectura-logica.md`](03-arquitectura-logica.md) | Módulos, responsabilidades, flujo de eventos |
| [`04-algoritmos.md`](04-algoritmos.md) | Asignación inicial, rebalanceo, búsqueda local |
| [`05-capacidad.md`](05-capacidad.md) | Demanda, capacidad, déficit, estados de factibilidad |
| [`06-estimador-de-duracion.md`](06-estimador-de-duracion.md) | EMA por empleado/tipo, trabajo restante, arranque en frío |
| [`07-persistencia.md`](07-persistencia.md) | Modelo de datos PostgreSQL |
| [`08-api.md`](08-api.md) | API REST, idempotencia y concurrencia |
| [`09-metricas.md`](09-metricas.md) | Métricas operativas y de calidad de predicción |
| [`10-plan-de-implementacion.md`](10-plan-de-implementacion.md) | Fases de implementación |
| [`11-decisiones-abiertas.md`](11-decisiones-abiertas.md) | Decisiones tomadas y pendientes |
| [`12-rust-y-solucionador.md`](12-rust-y-solucionador.md) | Stack Rust e interconexión con HiGHS |
| [`13-contrato-json.md`](13-contrato-json.md) | Contrato `POST /v1/plan` (+ [`schema/`](schema/)) |

## Invariantes fundamentales

- **Ninguna operación de rebalanceo puede cambiar el empleado de una actividad que
  ya comenzó.**
- Una actividad no puede iniciarse simultáneamente por dos empleados; esto se
  protege en la base de datos, no solo en la lógica.
- Las asignaciones *propuestas* se mantienen separadas de las *aplicadas*, para
  comparar planes sin modificar la operación.

## Terminología

- **Actividad** (`task`): unidad de trabajo a planificar.
- **Empleado** (`employee`): recurso con habilidades, velocidad y calendario.
- **Makespan**: tiempo global de finalización proyectado, `max(L_i)`.
- **Rebalanceo**: recálculo de asignaciones pendientes ante un cambio de estado.
- **Insuficiencia**: imposibilidad de cubrir la demanda con la capacidad modelada.
