# Benchmarks medidos del motor `highs`

> Valores medidos en el entorno descrito abajo. Son objetivos registrados,
> no garantías universales de latencia.

## Entorno

| Campo | Valor |
|---|---|
| Fecha (UTC) | 2026-10-14T20:44:06+00:00 |
| Sistema | Windows-11-10.0.26300-SP0 |
| Máquina | AMD64 |
| Procesador | AMD64 Family 23 Model 24 Stepping 1, AuthenticAMD |
| CPUs | 8 |
| Python | 3.12.10 |
| highs-api | 0.1.0 |
| HiGHS (highspy) | 1.15.1 |
| Presolve | choose |

## Resultados

| Caso | Repeticiones | Mejor wall (ms) | Mediana wall (ms) | solve_time_ms (motor) | Estado | Objetivo |
|---|---:|---:|---:|---:|---|---:|
| LP 100x50 | 3 | 4.86 | 5.18 | 2.50 | optimal | 156.19 |
| MIP 50 binarias | 3 | 42.54 | 48.03 | 45.94 | optimal | 913 |
| QP 100 variables | 3 | 13.93 | 16.72 | 5.70 | optimal | -1.41833 |

Notas:

- `wall` incluye validación, conversión a HiGHS y resolución; `solve_time_ms`
  solo la llamada a `run()`.
- Los datos de entrada son deterministas (semillas fijas) y se generan en
  `benchmarks/run_benchmarks.py`; un cambio de semilla cambia el problema.
- No se usan estos valores como umbral de CI compartida.
