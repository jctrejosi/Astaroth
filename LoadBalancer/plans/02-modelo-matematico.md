# 02 — Modelo matemático

El problema es una variante de **scheduling con máquinas paralelas no idénticas**:
cada empleado es un recurso con capacidades y tiempos de ejecución diferentes.

## Variables principales

Sea:

- $E$: conjunto de empleados.
- $J$: conjunto de actividades pendientes.
- $p_{ij}$: duración estimada de la actividad $j$ si la realiza el empleado $i$.
- $r_i$: tiempo restante de la actividad que el empleado $i$ está ejecutando;
  $0$ si está libre.
- $x_{ij}$: variable binaria, $1$ si la actividad $j$ se asigna al empleado $i$.
- $C_i(H)$: capacidad efectiva disponible del empleado $i$ durante el horizonte $H$.
- $d_j$: fecha límite de la actividad $j$, cuando exista.

Las actividades **en ejecución** se consideran fijas: no entran en el conjunto de
decisiones de reasignación; únicamente se contabiliza su tiempo restante ($r_i$).

## Carga proyectada por empleado

Si cada empleado realiza una actividad a la vez y las tareas pendientes no tienen
restricciones de secuencia especiales:

$$
L_i = r_i + \sum_{j \in J} p_{ij} x_{ij}
$$

$L_i$ es el tiempo de trabajo proyectado para el empleado. No implica que todas
las actividades deban completarse dentro del turno actual: depende de la capacidad
y del horizonte evaluado.

## Makespan

El tiempo global de finalización proyectado es:

$$
M = \max_{i \in E} L_i
$$

El objetivo principal es **minimizar $M$**, sujeto a que cada actividad se asigne
exactamente una vez:

$$
\sum_{i \in E} x_{ij} = 1 \qquad \forall j \in J
$$

Si un empleado no tiene las habilidades necesarias para una actividad, la
asignación queda **prohibida** ($x_{ij}=0$).

## Restricciones de capacidad

Para un horizonte específico, la capacidad se calcula descontando pausas,
ausencias y otros períodos no productivos. Si $C_i(H)$ es la capacidad total de
trabajo disponible desde el instante actual:

$$
r_i + \sum_{j} p_{ij} x_{ij} \le C_i(H)
$$

Esta restricción se aplica **cuando se exige** que todo el trabajo seleccionado
termine dentro de ese horizonte.

Si las actividades pueden continuar en turnos posteriores, el modelo debe
permitirlas en períodos futuros, con sus calendarios y disponibilidad. **No** debe
declararse falta de capacidad a largo plazo solo porque la demanda supere las horas
restantes del turno actual.

## Objetivos secundarios

Tras minimizar el makespan, se optimizan criterios en este orden configurable:

1. Cumplimiento de fechas límite y prioridades.
2. Reducción de sobrecargas evitables.
3. Reducción de reasignaciones innecesarias.
4. Disminución del tiempo ocioso cuando sea relevante.
5. Equilibrio de carga entre empleados comparables.

> **No** minimizar simplemente la diferencia entre el empleado más cargado y el
> menos cargado: si un empleado es mucho más rápido o tiene habilidades
> especializadas, una distribución desigual en horas puede ser la mejor solución.

## Función objetivo (orden lexicográfico)

Para comparar planes se usa optimización lexicográfica:

1. Minimizar violaciones de **restricciones duras** (idealmente cero).
2. Minimizar actividades que incumplen plazos, ponderadas por prioridad.
3. Minimizar el makespan.
4. Minimizar cambios de asignación innecesarios.
5. Mejorar criterios secundarios de balance.

Si se usa una suma ponderada, los pesos deben elegirse para que una mejora pequeña
en un criterio secundario **nunca** compense una violación de un criterio
prioritario.
