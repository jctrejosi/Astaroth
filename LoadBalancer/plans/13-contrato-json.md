# 13 — Contrato JSON `POST /v1/plan`

Contrato formal (esquemas en [`schema/`](schema/)). El servicio es **stateless**:
todo lo necesario para el cálculo llega en la petición y se devuelve en la
respuesta.

## Solicitud

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `horizon_minutes` | `integer ≥ 0` | sí | Horizonte de planificación |
| `employees` | `array<Employee>` | sí | Recursos disponibles |
| `tasks` | `array<Task>` | sí | Actividades a planificar |
| `options` | `Options` | no | Parámetros del solver |

### `Employee`

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `id` | `string` | sí | Identificador único |
| `available_minutes` | `integer ≥ 0` | no (def. `0`) | Capacidad efectiva en el horizonte |
| `skills` | `array<string>` | no (def. `[]`) | Tipos de actividad que puede realizar |
| `shifts` | `array<Shift>` | no | Calendario (disponibilidad por tramos) |

### `Shift`

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `start_minutes` | `integer ≥ 0` | sí | Inicio del tramo (offset) |
| `end_minutes` | `integer ≥ 0` | sí | Fin del tramo (offset) |

### `Task`

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `id` | `string` | sí | Identificador único |
| `status` | `pending` \| `assigned` \| `running` | sí | Estado operativo |
| `type` | `string` | sí | Tipo de actividad |
| `current_employee_id` | `string \| null` | no | Asignación actual (para `changes`) |
| `employee_id` | `string \| null` | no | Empleado que ejecuta (si `running`) |
| `remaining_minutes` | `integer ≥ 0 \| null` | no | Tiempo restante estimado (si `running`) |
| `estimated_minutes_by_employee` | `object<string, integer>` | no | Duración estimada por empleado |
| `priority` | `integer ≥ 0` | no (def. `0`) | Prioridad (mayor = más importante) |
| `deadline_minutes` | `integer ≥ 0 \| null` | no | Plazo en offset de minutos |
| `dependencies` | `array<string>` | no (def. `[]`) | Ids que deben completarse antes |

### `Options`

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `solver` | `"heuristic"` \| `"highs"` | no (def. `heuristic`) | Estrategia |
| `time_limit_seconds` | `number ≥ 0 \| null` | no | Límite del optimizador |
| `enforce_capacity` | `boolean` | no (def. `true`) | Exigir terminar en el horizonte |

## Respuesta

| Campo | Tipo | Descripción |
|---|---|---|
| `status` | `FEASIBLE` \| `CAPACITY_SHORTAGE` \| `UNASSIGNABLE` \| `UNKNOWN` | Resultado |
| `makespan_minutes` | `integer \| null` | Makespan proyectado |
| `assignments` | `array<Assignment>` | Plan completo propuesto |
| `running_tasks_unchanged` | `array<string>` | Actividades en ejecución no tocadas |
| `changes` | `array<Change>` | Cambios frente a `current_employee_id` |
| `capacity` | `CapacityReport` | Demanda, capacidad y déficit |
| `unassigned_tasks` | `array<string>` | Actividades sin empleado elegible |
| `solver` | `SolverInfo` | Método y optimalidad |
| `warnings` | `array<string>` | Avisos (p. ej. `DEADLINE_RISK`) |

### `Assignment`

| Campo | Tipo | Descripción |
|---|---|---|
| `task_id` | `string` | Id de la actividad |
| `employee_id` | `string` | Empleado asignado |

### `Change`

| Campo | Tipo | Descripción |
|---|---|---|
| `task_id` | `string` | Id de la actividad |
| `from_employee_id` | `string \| null` | Asignación previa |
| `to_employee_id` | `string` | Nueva asignación |
| `reason` | `string` | Motivo (`lower_projected_makespan`, `skill_scarcity`, …) |

### `CapacityReport`

| Campo | Tipo | Descripción |
|---|---|---|
| `required_minutes` | `integer` | Trabajo requerido (running + pendiente, mejor caso) |
| `available_minutes` | `integer` | Suma de capacidad efectiva |
| `shortage_minutes` | `integer` | `max(0, required - available)` |

### `SolverInfo`

| Campo | Tipo | Descripción |
|---|---|---|
| `method` | `string` | `greedy_local_search` \| `highs_mip` |
| `optimality_proven` | `boolean` | `true` solo con solver exacto (`optimal`) |

## Reglas

- Las tareas `running` **nunca** se reasignan: aparecen en
  `running_tasks_unchanged` y no en `assignments` ni `changes`.
- Una tarea pendiente sin ningún empleado elegible → `UNASSIGNABLE`.
- `shortage_minutes > 0` → `CAPACITY_SHORTAGE` (cuando `enforce_capacity=true`).
- Devolver **plan completo + cambios** para que el cliente valide y almacene.
