# 06 — Estimador de duración

La calidad del balanceador depende de la calidad de sus predicciones.

> **Stateless**: el balanceador **no** persiste observaciones. El aprendizaje
> (EMA, medias por equipo, etc.) vive en la **aplicación cliente**. En cada
> `POST /v1/plan` el cliente envía las estimaciones ya calculadas
> (`estimated_minutes_by_employee`) o los datos históricos necesarios. La API no
> recuerda observaciones entre llamadas.

## Qué se registra (por combinación empleado × tipo de actividad)

- Duración prevista.
- Duración real.
- Tiempo activo frente a pausas.
- Complejidad de la actividad.
- Fecha y turno.
- Circunstancias excepcionales.
- Cantidad de observaciones disponibles.

## Primera versión: media móvil exponencial (EMA)

$$
\hat{t}_{n} = \alpha t_n + (1 - \alpha)\,\hat{t}_{n-1}
$$

- $t_n$: duración real observada.
- $\hat{t}_n$: estimación actualizada.
- $\alpha$: peso de las observaciones recientes.

Un $\alpha$ alto adapta rápido pero es más sensible a valores atípicos.

### Modelo jerárquico (arranque en frío)

- Usar un modelo **por empleado y tipo de actividad** cuando haya datos suficientes.
- Para empleados nuevos o combinaciones con pocas observaciones, recurrir
  progresivamente a la **media del equipo** para esa actividad.

## Predicción de trabajo restante

Para una actividad en ejecución **no** se vuelve a sumar su duración original. Se
estima el tiempo restante a partir del progreso real.

Ejemplo: si se estimó 40 min y ya lleva 25, no implica que queden 15: puede haber
progreso parcial, pausas o una estimación inicial incorrecta.

El estimador distingue entre:

- Duración total prevista.
- Tiempo ya transcurrido.
- Progreso observado.
- Tiempo restante estimado.
- Incertidumbre de la estimación.

El **tiempo restante** se usa en la planificación, pero la actividad sigue **fijada**
a su empleado actual.
