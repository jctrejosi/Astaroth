"""Reglas de limpieza del legado Advantage (descubiertas en la migración Mercaldas).

Conocimiento duro que no debe duplicarse en cada pipeline: centinelas de vacío,
fechas AAAAMMDD, codificación y la anomalía del bulk. El servicio de sync y
cualquier ingesta de .ADT importan estas reglas desde aquí.
"""

import datetime

# Centinelas de "vacío" por tipo numérico (Advantage los usa como NULL).
EMPTY_DOUBLE = 0x8000000000000020
EMPTY_INT = -2147483648
EMPTY_SHORT = -32768

# Fecha del bulk anómalo: 55,3M líneas en un solo día que no son ventas reales.
ANOMALIA_BULK_FECHA = datetime.date(2026, 5, 14)

# Regla de join de clientes: el identificador en las ventas (IFCLIENTE) es la
# cédula/NIT, no el código interno CODCLI. Match 99,1% contra clientes.cedula.
# Ver NOTAS_LEGADO.md.
VENTAS_CLIENTE_KEY = "cedula"

# Codificación del legado (Windows latino).
ENCODING = "cp1252"


def fecha_yyyymmdd(v) -> datetime.date | None:
    """Convierte un valor AAAAMMDD (int, float o str ISO) en date, o None si es inválido.

    Cubre los casos que aparecen en el legado: enteros como 20240101, flotantes
    como 20240101.0 (doble precisión que guarda la fecha) y cadenas ISO.
    """
    if v is None or v == "":
        return None
    if isinstance(v, str):
        try:
            return datetime.date.fromisoformat(v)
        except ValueError:
            return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and 10000000 <= int(v) <= 99999999:
        n = int(v)
        try:
            return datetime.date(n // 10000, (n // 100) % 100, n % 100)
        except ValueError:
            return None
    return None


def es_anomalia_bulk(fecha) -> bool:
    """True si la fecha es la del bulk anómalo (debe excluirse de las métricas)."""
    return fecha == ANOMALIA_BULK_FECHA
