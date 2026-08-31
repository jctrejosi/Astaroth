"""Lector de solo lectura para tablas Advantage Database Server (.ADT).

Entiende el formato de cabecera (400 bytes) y descriptores de columna (200
bytes cada uno), y decodifica los tipos de campo más comunes, incluidas las
particularidades del legado Mercaldas (centinelas de vacío, fechas AAAAMMDD).

Basado en el formato documentado por Chase Gray (Ruby-ADT) y Albert Zak
(node_adt), corregido con los hallazgos de la migración real.
"""

import datetime
import struct

HEADER_LENGTH = 400
COLUMN_LENGTH = 200
JULIAN_1970 = 2440588
MS_PER_DAY = 86400000

# Centinelas de "vacío" usados por Advantage en lugar de NULL.
EMPTY_DOUBLE = 0x8000000000000020
EMPTY_INT = -2147483648
EMPTY_SHORT = -32768

# Códigos de tipo de campo de Advantage Database Server.
FIELD_TYPES = {
    1: "Logical",
    2: "Numeric",
    3: "Date",
    4: "Character",
    5: "Memo",
    6: "Binary",
    7: "Image",
    8: "Varchar",
    9: "CompactDate",
    10: "Double",
    11: "Integer",
    12: "ShortInt",
    13: "Time",
    14: "Timestamp",
    15: "AutoInc",
    16: "Raw",
    17: "CurDouble",
    18: "Money",
    19: "Double",
    20: "CiChar",
    21: "Numeric",
    22: "Varchar",
    26: "NChar",
    28: "NVarChar",
}


class AdtTable:
    def __init__(self, path, encoding="cp1252"):
        self.path = path
        self.encoding = encoding
        self.f = open(path, "rb")

        hdr = self.f.read(HEADER_LENGTH)
        if len(hdr) < HEADER_LENGTH:
            raise ValueError(f"{path}: archivo demasiado pequeño")

        if hdr[:16].rstrip(b"\x00") != b"Advantage Table":
            raise ValueError(f"{path}: no parece una tabla Advantage (.ADT)")

        self.record_count = struct.unpack_from("<I", hdr, 24)[0]
        self.data_offset = struct.unpack_from("<I", hdr, 32)[0]
        self.record_length = struct.unpack_from("<I", hdr, 36)[0]
        self.column_count = (self.data_offset - HEADER_LENGTH) // COLUMN_LENGTH

        self.columns = []
        self.f.seek(HEADER_LENGTH)
        for _ in range(self.column_count):
            raw = self.f.read(COLUMN_LENGTH)
            if len(raw) < COLUMN_LENGTH:
                break
            name = raw[:128].split(b"\x00", 1)[0].decode(self.encoding, "replace").strip()
            type_code = struct.unpack_from("<H", raw, 129)[0]
            length = struct.unpack_from("<H", raw, 135)[0]
            if length > 0:
                self.columns.append({
                    "name": name,
                    "type": type_code,
                    "length": length,
                })
        self.column_count = len(self.columns)

    def close(self):
        self.f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def iter_records(self, offset=0, limit=None, filter_fn=None):
        """Genera diccionarios {nombre_columna: valor}.

        filter_fn(rec) recibe el registro crudo (bytes) y devuelve False para
        saltarlo SIN decodificarlo.

        El primer byte del registro no es una marca de borrado fiable
        (es 0x04 en tablas v2 y 0x05 en v1), así que se leen todos los
        registros, igual que hace Ruby-ADT.
        """
        total = self.record_count
        end = total if limit is None else min(total, offset + limit)
        i = offset
        while i < end:
            pos = self.data_offset + self.record_length * i
            self.f.seek(pos)
            rec = self.f.read(self.record_length)
            if len(rec) < self.record_length:
                break
            if filter_fn is not None and not filter_fn(rec):
                i += 1
                continue
            yield self._decode_record(rec)
            i += 1

    def _decode_record(self, rec):
        body = rec[5:]  # 5 bytes de prefijo (tipo de registro + 4 desconocidos)
        out = {}
        pos = 0
        for col in self.columns:
            ln = col["length"]
            field = body[pos:pos + ln]
            pos += ln
            out[col["name"]] = self._decode_field(col["type"], field, col["name"])
        return out

    def _decode_field(self, type_code, buf, name=""):
        t = FIELD_TYPES.get(type_code)
        try:
            if t in ("Character", "CiChar", "Varchar"):
                return buf.split(b"\x00", 1)[0].decode(self.encoding, "replace").rstrip()
            if t in ("NChar", "NVarChar"):
                return buf.decode("utf-16-le", "replace").split("\x00", 1)[0].rstrip()
            if t == "Logical":
                c = buf[:1].decode(self.encoding, "replace")
                return c in ("T", "t", "Y", "y", "1")
            if t == "Date":
                julian = struct.unpack_from("<i", buf, 0)[0]
                if julian == 0:
                    return None
                return datetime.date(1970, 1, 1) + datetime.timedelta(days=julian - JULIAN_1970)
            if t == "Timestamp":
                julian = struct.unpack_from("<i", buf, 0)[0]
                ms = struct.unpack_from("<i", buf, 4)[0]
                if julian == 0 and ms == -1:
                    return None
                base = datetime.datetime(1970, 1, 1) + datetime.timedelta(days=julian - JULIAN_1970)
                return base + datetime.timedelta(milliseconds=ms)
            if t == "Time":
                ms = struct.unpack_from("<i", buf, 0)[0]
                if ms < 0:
                    return None
                return str(datetime.timedelta(milliseconds=ms))
            if t in ("Double", "CurDouble"):
                if len(buf) >= 8 and struct.unpack_from("<Q", buf, 0)[0] == EMPTY_DOUBLE:
                    return None
                v = struct.unpack_from("<d", buf, 0)[0]
                if _looks_like_date(name):
                    if v == 0.0:
                        return None
                    d = _format_yyyymmdd(int(v))
                    return d if d is not None else v
                return v
            if t == "Integer":
                v = struct.unpack_from("<i", buf, 0)[0]
                if v == EMPTY_INT:
                    return None
                if _looks_like_date(name):
                    if v == 0:
                        return None
                    d = _format_yyyymmdd(v)
                    return d if d is not None else v
                return v
            if t == "ShortInt":
                v = struct.unpack_from("<h", buf, 0)[0]
                return None if v == EMPTY_SHORT else v
            if t == "AutoInc":
                return struct.unpack_from("<I", buf, 0)[0]
            if t == "Numeric":
                return _decode_numeric(buf)
            if t == "Money":
                return _decode_money(buf)
            if t == "Memo":
                return {"memo": struct.unpack_from("<I", buf, 0)[0]}
            if t in ("Binary", "Image", "Raw"):
                return buf.hex()
        except Exception:
            pass
        return f"<raw:{buf.hex()}>"


def _looks_like_date(name):
    n = name.upper()
    return "FECHA" in n or "FCH" in n


def _format_yyyymmdd(v):
    if not (10000000 <= v <= 99999999):
        return None
    y = v // 10000
    m = (v // 100) % 100
    d = v % 100
    try:
        return datetime.date(y, m, d).isoformat()
    except ValueError:
        return None


def _decode_numeric(buf):
    """Advantage NUMERIC: BCD empaquetado, último nibble = signo (0x0C=+, 0x0D=-)."""
    if not buf:
        return None
    sign = 1
    digits = []
    for byte in buf[:-1]:
        digits.append((byte >> 4) & 0x0F)
        digits.append(byte & 0x0F)
    last = buf[-1]
    digits.append((last >> 4) & 0x0F)
    low = last & 0x0F
    if low == 0x0D:
        sign = 1
    elif low == 0x0C:
        sign = 1
    elif low in (0x0B, 0x0F):
        sign = -1
    s = "".join(str(d) for d in digits if d < 10)
    if not s:
        return None
    return sign * int(s)


def _decode_money(buf):
    """Advantage MONEY: entero de 64 bits con 4 decimales implícitos."""
    if len(buf) < 8:
        return None
    v = struct.unpack_from("<q", buf, 0)[0]
    return v / 10000.0
