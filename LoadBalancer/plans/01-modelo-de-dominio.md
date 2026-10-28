# 01 — Modelo de dominio

> Estos conceptos describen el dominio. En la arquitectura stateless viven en la
> **aplicación cliente** y llegan al balanceador como instantánea en cada
> `POST /v1/plan` (ver [`07-persistencia.md`](07-persistencia.md)).

## Empleado (`employee`)

| Campo | Descripción |
|---|---|
| `employee_id` | Identificador único |
| `status` | Disponible, ocupado, ausente o inactivo |
| `skills` | Tipos de actividad que puede realizar |
| `speed_profile` | Velocidad estimada por tipo de actividad |
| `shift_calendar` | Turnos y horarios de disponibilidad |
| `capacity_limit` | Límites operativos adicionales, si existen |
| `current_task_id` | Actividad actualmente en ejecución |
| `available_at` | Próximo momento estimado de disponibilidad |

La **capacidad no es un número fijo**: se calcula para un horizonte determinado
(p. ej. próximos 30 minutos, resto del turno o próximas 24 horas). Ver
[`05-capacidad.md`](05-capacidad.md).

### Habilidades y niveles

`employee_skills` asocia a cada empleado un `task_type` y, opcionalmente, un nivel
o grado de competencia. La elegibilidad de un empleado para una actividad deriva
de esta relación (y de su `status`/disponibilidad).

## Actividad (`task`)

| Campo | Descripción |
|---|---|
| `task_id` | Identificador único |
| `task_type` | Tipo de actividad |
| `status` | Pendiente, asignada, en ejecución, completada o bloqueada |
| `priority` | Importancia operativa |
| `created_at` | Fecha de creación |
| `deadline` | Fecha límite, si existe |
| `estimated_duration` | Duración estimada **para un empleado concreto** |
| `assigned_employee_id` | Empleado asignado |
| `started_at` / `completed_at` | Tiempos reales |
| `dependencies` | Actividades que deben completarse antes |

Las duraciones se calculan **por combinación de empleado y tipo de actividad**, no
como un único promedio global. Por eso `estimated_duration` se materializa por
asignación (ver [`06-estimador-de-duracion.md`](06-estimador-de-duracion.md)).

### Ciclo de vida

```
pendiente → asignada → en ejecución → completada
                 │
                 └────────────→ bloqueada (por dependencia / insuficiencia)
```

Transiciones clave:

- `pendiente → asignada`: el balanceador propone un empleado.
- `asignada → en ejecución`: el empleado inicia la actividad; queda **fijada**.
- `en ejecución → completada`: se registra el tiempo real.
- Cualquier estado → `bloqueada`: cuando no puede planificarse (p. ej. depende de
  otra actividad, o no hay empleado elegible).

## Plan de asignación (`planning_run`)

Se mantiene una entidad por **versión del plan** para auditar decisiones:

- `plan_id` y `version`.
- Fecha de cálculo.
- Estado operativo utilizado para calcularlo.
- Asignaciones propuestas.
- Métricas del plan (makespan, plazos, etc.).
- Motivo del rebalanceo.
- Cambios aplicados y rechazados.

Permite responder **por qué** se reasignó una actividad y comparar el plan
anterior con el nuevo.
