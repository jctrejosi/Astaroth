# 08 — Contrato de la API

Servicio **stateless**. Endpoint principal:

```
POST /v1/plan
```

## Solicitud

```json
{
  "horizon_minutes": 480,
  "employees": [
    { "id": "E1", "available_minutes": 420, "skills": ["packing", "labeling"] },
    { "id": "E2", "available_minutes": 420, "skills": ["packing"] }
  ],
  "tasks": [
    {
      "id": "T1",
      "status": "pending",
      "current_employee_id": "E2",
      "type": "packing",
      "estimated_minutes_by_employee": { "E1": 15, "E2": 25 }
    },
    {
      "id": "T2",
      "status": "pending",
      "type": "labeling",
      "estimated_minutes_by_employee": { "E1": 20 }
    },
    {
      "id": "T3",
      "status": "running",
      "employee_id": "E1",
      "remaining_minutes": 10
    }
  ]
}
```

Es un ejemplo simplificado. En producción incluiría además prioridades, plazos
(`deadline`), dependencias y restricciones adicionales según el proceso.

> **Nota**: los valores del ejemplo son ilustrativos; en particular, `assignments`
> y `makespan_minutes` no son necesariamente el óptimo matemático del ejemplo.

## Respuesta

```json
{
  "status": "FEASIBLE",
  "makespan_minutes": 35,
  "assignments": [
    { "task_id": "T1", "employee_id": "E1" },
    { "task_id": "T2", "employee_id": "E1" }
  ],
  "running_tasks_unchanged": ["T3"],
  "changes": [
    { "task_id": "T1", "from_employee_id": "E2", "to_employee_id": "E1", "reason": "lower_projected_makespan" }
  ],
  "capacity": {
    "required_minutes": 45,
    "available_minutes": 840,
    "shortage_minutes": 0
  },
  "unassigned_tasks": [],
  "solver": { "method": "greedy_local_search", "optimality_proven": false }
}
```

### Decisiones de contrato

- **Devolver ambos**: el plan propuesto completo (`assignments`) **y** la lista de
  cambios (`changes`). Facilita que la aplicación valide y almacene.
- `running_tasks_unchanged`: actividades en ejecución que se mantienen fijas.
- `unassigned_tasks`: actividades que no pudieron asignarse.

### Estados (`status`)

Distinguir al menos:

- `FEASIBLE`
- `CAPACITY_SHORTAGE`
- `UNASSIGNABLE`
- `UNKNOWN`

No poder encontrar una solución **no** siempre significa que sea matemáticamente
imposible (por eso `UNKNOWN` ≠ `CAPACITY_SHORTAGE`). Ver
[`05-capacidad.md`](05-capacidad.md).

## Concurrencia e idempotencia

- El servicio no muta estado: cada `POST /v1/plan` es una operación **pura** sobre
  el snapshot recibido.
- La aplicación cliente es responsable de la concurrencia (versión de estado) y de
  aplicar los cambios de forma atómica.
- La API no permite reasignar directamente una actividad en ejecución: las tareas
  `running` se devuelven en `running_tasks_unchanged` y nunca entran en `changes`.
