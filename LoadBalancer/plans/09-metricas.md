# 09 — Métricas y observabilidad

El sistema debe demostrar que mejora el funcionamiento real, no solo que produce
planes aparentemente equilibrados.

## Eficiencia del plan

- Makespan previsto y real.
- Tiempo medio de finalización.
- Cumplimiento de fechas límite.
- Tiempo ocioso evitable.

## Capacidad

- Demanda estimada frente a capacidad efectiva.
- Horas de déficit por horizonte.
- Empleados y habilidades que limitan la producción.
- Actividades sin empleados elegibles.

## Estabilidad

- Número de reasignaciones.
- Cambios descartados por estado obsoleto.
- Tiempo de cálculo del optimizador.
- Porcentaje de eventos que provocan un rebalanceo.

## Calidad de las predicciones

- Error absoluto medio de duración (MAE).
- Error de predicción por tipo de actividad.
- Diferencia entre duración prevista y real.
- Cantidad y antigüedad de las observaciones utilizadas.

## Validación contra referencias

Comparar el algoritmo con dos líneas base:

1. **FIFO**.
2. **Menor carga estimada**.

Ejecutar las tres estrategias con los **mismos** conjuntos de actividades y
restricciones. Con registros históricos, reproducir eventos pasados en orden
temporal; para capacidad, incluir los momentos en que la demanda superó los
recursos.
