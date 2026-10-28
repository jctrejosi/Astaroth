# 05 — Detector de capacidad insuficiente

Módulo **independiente** del optimizador. Responde:

> ¿Podemos completar la demanda con los recursos disponibles, dentro del plazo
> requerido?

## Demanda y capacidad

Para un horizonte $H$:

- $W(H)$: trabajo requerido dentro del horizonte.
- $C_{\text{total}}(H) = \sum_i C_i(H)$.

Déficit agregado:

$$
D(H) = \max(0,\; W(H) - C_{\text{total}}(H))
$$

Utilización requerida:

$$
U(H) = \frac{W(H)}{C_{\text{total}}(H)}
$$

Ejemplo: 80 h de trabajo requerido y 64 h de capacidad efectiva → déficit de
16 h y utilización requerida del **125 %**.

> Este cálculo usa **horas de trabajo comparables**. Si las duraciones ya están
> estimadas según la velocidad individual de cada empleado, **no** aplicar de nuevo
> un factor de productividad a esas mismas horas.

## Por qué el total no basta

20 h de actividades especializadas con un único empleado habilitado (8 h
disponibles) no se resuelven con 30 h libres del resto del equipo: la restricción
es de **habilidad**, no de horas.

El detector analiza:

- Capacidad total disponible.
- Capacidad **por tipo de actividad / habilidad**.
- Elegibilidad de cada empleado.
- Plazos individuales.
- Dependencias entre actividades.
- Disponibilidad real dentro del calendario.
- Incertidumbre de las duraciones estimadas.

> El análisis por tipo de actividad es una aproximación; las restricciones
> combinadas (habilidades + plazos + secuencias) pueden exigir resolver el problema
> de planificación completo para confirmar factibilidad.

## Estados que produce

| Estado | Significado |
|---|---|
| `FEASIBLE` | Existe una planificación que satisface las restricciones evaluadas |
| `OVERLOADED` | La carga supera la capacidad en uno o más recursos |
| `CAPACITY_SHORTAGE` | La demanda no puede cubrirse con la capacidad disponible bajo las restricciones modeladas |
| `DEADLINE_RISK` | Alguna actividad tiene alta probabilidad de incumplir su plazo |
| `UNASSIGNABLE` | Una actividad no tiene ningún empleado elegible |
| `UNKNOWN` | No hay datos suficientes o el optimizador agotó su tiempo sin confirmar factibilidad |

> Distinguir `CAPACITY_SHORTAGE` de `UNKNOWN`: que el optimizador no encuentre
> solución dentro del tiempo permitido **no demuestra** que no exista.

## Estimación de recursos adicionales

Simulaciones posibles:

- Añadir un empleado con determinadas habilidades.
- Extender un turno.
- Incorporar horas extra.
- Redistribuir actividades entre turnos.
- Aplazar actividades de menor prioridad.
- Modificar la asignación de habilidades (cuando sea posible).

La salida no se limita a «falta un empleado»: debe **cuantificar el déficit**,
identificar la **habilidad limitante** y presentar escenarios comparables. La
cantidad de empleados adicionales depende de sus velocidades, habilidades, jornadas
y del plazo.
