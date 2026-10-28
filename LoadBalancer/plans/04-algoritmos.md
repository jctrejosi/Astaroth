# 04 — Algoritmos

## 1. Asignación inicial

Debe ser rápida, determinista cuando sea posible y suficientemente buena como
punto de partida del optimizador.

**Estrategia: asignación por menor makespan proyectado.**

1. Obtener todas las actividades pendientes que pueden planificarse.
2. Calcular la duración estimada de cada actividad para cada empleado elegible.
3. Inicializar las cargas con el tiempo restante de las actividades en ejecución.
4. Ordenar las actividades por dificultad o duración estimada, colocando primero
   las que puedan generar más problemas de planificación.
5. Para cada actividad, probar su asignación a cada empleado elegible.
6. Calcular el makespan resultante de cada alternativa.
7. Elegir la asignación que produce el mejor resultado, respetando prioridades,
   plazos y restricciones.
8. Actualizar las cargas y continuar con la siguiente actividad.

> **Nota sobre la ordenación**: es una heurística. Cuando los tiempos dependen del
> empleado, no existe un único valor de duración que ordene perfectamente las
> tareas. Se puede empezar usando la **duración mínima entre empleados elegibles**
> junto con una **medida de escasez de habilidades** para evitar que las tareas
> especializadas queden sin recursos.

## 2. Rebalanceo dinámico

Trabaja **exclusivamente** con actividades pendientes o asignadas que aún no han
comenzado.

### Operaciones permitidas

| Operación | Descripción |
|---|---|
| **Movimiento** | Trasladar una actividad pendiente de un empleado a otro elegible |
| **Intercambio** | Intercambiar dos actividades pendientes entre empleados, cuando ambos puedan realizarlas |
| **Reasignación de grupo** | Evaluar un conjunto de actividades cuando los movimientos individuales no mejoran (p. ej. por habilidades limitadas) |

### Función objetivo

Optimización lexicográfica (ver [`02-modelo-matematico.md`](02-modelo-matematico.md)):

1. Violaciones de restricciones duras.
2. Actividades que incumplen plazos, ponderadas por prioridad.
3. Makespan.
4. Cambios de asignación innecesarios.
5. Criterios secundarios de balance.

### Requisitos de producción

- **Límite de tiempo** para la optimización.
- **Evitar ciclos** (no reintentar indefinidamente el mismo movimiento).
- **Evaluación incremental** de cambios cuando sea posible.
- Conservar el **mejor plan válido encontrado** hasta el momento.

> Una búsqueda local no garantiza el óptimo global. Si el tamaño o las
> restricciones lo requieren, sustituir por OR-Tools CP-SAT u otro solucionador
> (sin cambiar `duration_estimator`).

## 3. Evitar rebalanceo excesivo

Mecanismos para que una actividad no cambie de empleado repetidamente por
variaciones pequeñas:

- **Umbral de mejora**: no aplicar un cambio si la mejora prevista es insignificante.
- **Coste de reasignación**: considerar el esfuerzo administrativo/operativo de mover.
- **Tiempo mínimo entre reasignaciones**: evitar movimientos repetidos salvo cambio importante.
- **Límite de cambios por ciclo**: restringir la cantidad de modificaciones.
- **Congelación al iniciar**: una vez que una actividad empieza, ya no puede moverse.

> El umbral debe configurarse según el contexto operativo, **no** como un
> porcentaje arbitrario para todos los casos.

## 4. Aplicación segura de los cambios

El planificador puede tardar varios segundos; durante ese tiempo una actividad
puede comenzar o terminar. Aplicar un plan obsoleto podría duplicar asignaciones o
mover una actividad en ejecución.

Flujo seguro:

1. Leer el estado actual y su **versión**.
2. Calcular un plan nuevo **sin modificar** las asignaciones operativas.
3. Validar el plan.
4. Abrir una transacción.
5. Comprobar que el estado relevante no haya cambiado.
6. Verificar que todas las actividades que se van a mover sigan pendientes.
7. Aplicar solo los cambios necesarios.
8. Registrar la versión y los motivos.
9. Confirmar la transacción.

Si el estado cambió durante la planificación, se **descarta o recalcula** el plan
afectado.

> **Invariante**: ninguna operación de rebalanceo puede cambiar el empleado de una
> actividad que ya comenzó. Además, impedir que una actividad sea iniciada a la vez
> por dos empleados debe protegerse **en la base de datos**.
