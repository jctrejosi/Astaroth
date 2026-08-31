# astaroth-core

Núcleo compartido de **Astaroth**: ingesta y limpieza del legado Advantage
Database Server + definiciones de features. **Sin dependencias de terceros**
(stdlib puro) para que el servicio de sync y los pipelines lo importen sin
fricción.

## Qué contiene

| Módulo | Qué hace |
|---|---|
| `astaroth_core.data.adt` | `AdtTable`: lector de solo lectura de `.ADT` (decodifica tipos, centinelas de vacío, fechas `AAAAMMDD`) |
| `astaroth_core.data.cleaning` | Reglas de limpieza descubiertas en la migración: centinelas, `fecha_yyyymmdd`, anomalía del bulk, encoding |
| `astaroth_core.features.rfm` | SQL versionado de la vista RFM (`analytics.vw_rfm_clientes`) |
| `astaroth_core.config` / `logging` | Utilidades mínimas de configuración y logging |

## Instalación

```bash
pip install -e /ruta/a/Astaroth/core
```

O, sin instalarlo, añade `Astaroth/core` al `PYTHONPATH`.

## Uso

```python
from astaroth_core import AdtTable, cleaning

with AdtTable("POSCLI.adt") as t:
    for rec in t.iter_records(limit=10):
        print(rec["CODCLI"], cleaning.fecha_yyyymmdd(rec.get("FECHAN")))
```

## Por qué existe

Con la réplica en Postgres como fuente para analytics/ML, este paquete **no**
es el camino de datos habitual; es la capa de **ingesta** (de `.ADT` a
Postgres) y la **fuente de verdad de las reglas de limpieza** del legado. El
servicio de sync es su único consumidor directo; el resto lee vistas SQL en
Postgres (definidas y versionadas aquí, en `features/`).
