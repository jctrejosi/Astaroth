# core

Librería compartida de **Astaroth**: ingesta y limpieza del legado Advantage
Database Server + bloques de features como el RFM. **Sin dependencias de
terceros** (stdlib puro).

## Estructura (plana, sin anidamiento)

```
core/
├── __init__.py        # paquete `core`
├── adt.py             # AdtTable: lector .ADT
├── cleaning.py        # reglas de limpieza del legado
├── config.py / logging.py
└── RFM/               # bloque de features RFM
    ├── rfm.py         # helper (genera el DDL de la vista)
    └── rfm_view.sql   # la vista SQL lista para aplicar en Postgres
```

## Uso

Añade `Astaroth/` al `PYTHONPATH` (este directorio `core/` es el paquete):

```bash
export PYTHONPATH=/ruta/a/Astaroth
```

```python
from core import AdtTable, cleaning, rfm_view_sql

with AdtTable("POSCLI.adt") as t:
    for rec in t.iter_records(limit=10):
        print(rec["CODCLI"], cleaning.fecha_yyyymmdd(rec.get("FECHAN")))

# DDL de la vista RFM (para crearla en la BD de analytics)
print(rfm_view_sql())
```

## Qué contiene

| Módulo | Qué hace |
|---|---|
| `core.adt` | `AdtTable`: lector de solo lectura de `.ADT` (tipos, centinelas de vacío, fechas `AAAAMMDD`) |
| `core.cleaning` | Reglas de limpieza del legado: centinelas, `fecha_yyyymmdd`, anomalía del bulk, encoding, join de clientes |
| `core.RFM` | RFM: vista SQL por cliente (`recencia`, `frecuencia`, `monetario`, ticket, categorías) que se materializa en la BD de analytics |
| `core.config` / `core.logging` | Utilidades mínimas |
| **`NOTAS_LEGADO.md`** | **Reglas del legado: join por cédula, fechas, centinelas, anomalías — léelo antes de tocar datos `pos.*`** |

## Por qué existe

Con la réplica en Postgres como fuente para analytics/ML, este paquete es la
capa de **ingesta** (de `.ADT` a Postgres) y la **fuente de verdad de las
reglas de limpieza** del legado, más los bloques de features compartidos
(RFM). El servicio de sync y los pipelines lo importan; los algoritmos viven
en los servicios de Astaroth (`clustering-api`, `XGBoost-api`, ...).
