# 07 — Persistencia y estado operativo

## El balanceador NO persiste estado

La API de balanceo es **stateless**:

- No tiene base de datos propia.
- No guarda la cola de actividades, las asignaciones vigentes ni el historial de
  tiempos.
- Solo puede conservar **logs técnicos** y **métricas de operación** (no son parte
  de su funcionamiento).

El estado operativo vive en la **aplicación cliente**.

## Qué debe enviar la aplicación en cada petición

Al no conservar estado, la API recibe los datos necesarios para cada cálculo:

| Dato de entrada | Para qué sirve |
|---|---|
| Empleados y habilidades | Determinar quién puede realizar cada actividad |
| Disponibilidad y capacidad por horizonte | Detectar límites operativos |
| Actividades pendientes | Calcular nuevas asignaciones |
| Actividades en ejecución y tiempo restante | Mantenerlas fijas y calcular su carga futura |
| Duración estimada por empleado y actividad | Comparar el coste de cada asignación |
| Asignaciones actuales | Calcular qué cambios son necesarios y evitar movimientos innecesarios |
| Prioridades, plazos y dependencias | Respetar las reglas de negocio |
| Horizonte de planificación | Determinar cuándo debe completarse el trabajo |

No es necesario enviar toda la base de datos de la aplicación: solo el conjunto de
información relevante para la planificación solicitada.

> Si la aplicación quiere que el balanceador **aprenda** de duraciones anteriores,
> debe enviar las estimaciones ya calculadas o los datos históricos necesarios en
> cada solicitud. Sin persistencia propia, la API **no puede recordar** observaciones
> entre llamadas.

## Modelo de datos de referencia (responsabilidad del cliente)

Las siguientes tablas describen el estado que la **aplicación cliente** debe
mantener. El balanceador las consume vía el contrato `POST /v1/plan`, no las
gestiona.

| Tabla | Función |
|---|---|
| `employees` | Datos, estado y límites operativos |
| `employee_skills` | Habilidades y niveles por tipo de actividad |
| `employee_shifts` | Turnos, ausencias y disponibilidad |
| `tasks` | Actividades y estado operativo |
| `task_dependencies` | Dependencias entre actividades |
| `task_assignments` | Asignaciones actuales e historial |
| `task_time_observations` | Tiempos reales y observaciones |
| `duration_models` | Estimaciones agregadas por empleado y actividad (se envían al balanceador) |
| `planning_runs` | Ejecuciones solicitadas y sus respuestas |
| `planning_assignments` | Asignaciones propuestas devueltas por el balanceador |
| `capacity_assessments` | Resultados de factibilidad devueltos |
| `planning_events` | Eventos que provocaron una replanificación |
| `audit_log` | Historial de cambios y sus motivos |

Las asignaciones **propuestas** (respuesta del balanceador) deben almacenarse
separadas de las **aplicadas**, para comparar soluciones sin modificar la operación.

## Integridad (en el cliente)

- **Versión de estado**: para detectar cambios entre que se lee el snapshot y se
  aplica la respuesta.
- **Unicidad de ejecución**: impedir que dos empleados inicien la misma actividad
  (a nivel de base de datos, no solo en la lógica).
- **Transacciones**: aplicar cambios de asignación de forma atómica.
- **Auditoría**: registrar versión, motivo y plan origen de cada cambio.
