# Notas del legado Advantage (Mercaldas)

Conocimiento descubierto durante la migración del sistema de tiendas. Está
aquí para no redescubrirlo a mano — consulta esto antes de tocar datos `pos.*`.

## Reglas de formato

| Regla | Detalle |
|---|---|
| Centinelas de vacío | `double` = `0x8000000000000020`, `short` = `-32768`, `int` = `-2147483648` → tratar como NULL (en `core/cleaning.py`) |
| Fechas | se guardan como número `AAAAMMDD` en campos `Integer` **y** `Double` (no es TDateTime) |
| Encoding | `cp1252` (Windows latino) |
| Anomalía del bulk | `2026-05-14`: 55,3M de filas que no son ventas reales → excluir siempre (`cleaning.es_anomalia_bulk`) |
| Registros borrados | el primer byte del registro NO es una marca fiable de borrado (`0x04`/`0x05` según versión) — se leen todos |

## 🔑 Regla del join de clientes (la importante)

**`pos.venta_lineas.cliente_cod` (campo `IFCLIENTE`) es la cédula/NIT del
cliente (identificación nacional), NO el código interno `CODCLI`.**

- ✅ Join correcto: `venta_lineas.cliente_cod = clientes.cedula` → **99,1% de match**
- ❌ No usar `clientes.codcli` (código interno de 13 dígitos `"2000..."`) → solo 13% de match
- El NIT (`nit_empresa`) casi no se captura en `clientes` (solo 11 registros); las empresas suelen matchear por su NIT dentro de `cedula`
- Quedan ~0,9% de códigos sin match: valores de prueba (`"+22222222222"`, `"0"`, `"1"`) — ignorarlos

Consecuencia: los segmentos y el RFM quedan claveados por cédula; cualquier
join con datos de contacto (email, celular, consentimientos) va por `cedula`.

## Calidad de datos observada

- 51 códigos `CODCLI` duplicados en `POSCLI` (al cargar se deduplica: primera ocurrencia)
- ~63% de los clientes sin fecha de nacimiento válida
- Fechas inválidas en el origen (p. ej. `1979-02-29`) → se cargan como NULL
- Solo 1.589 clientes segmentados tienen consentimiento de WhatsApp; el canal fuerte es email (~19K)
