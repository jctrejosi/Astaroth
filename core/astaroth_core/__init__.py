"""Astaroth core: ingesta y limpieza del legado Advantage + features compartidas.

Sin dependencias de terceros (stdlib puro) para que el servicio de sync y
cualquier pipeline lo importen sin fricción.
"""

__version__ = "0.1.0"

from astaroth_core.data.adt import AdtTable, FIELD_TYPES
from astaroth_core.data import cleaning

__all__ = ["AdtTable", "FIELD_TYPES", "cleaning", "__version__"]
