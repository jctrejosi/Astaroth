"""core: librería compartida de Astaroth — ingesta y limpieza del legado
Advantage + bloques de features (RFM). Sin dependencias de terceros.

Uso: añade `Astaroth/` al PYTHONPATH (o instala como subpaquete) y:
    from core import AdtTable, cleaning, rfm_view_sql
    from core.RFM import rfm_view_sql
"""

__version__ = "0.1.0"

from .adt import AdtTable, FIELD_TYPES
from . import cleaning
from .RFM import RFM_SQL, rfm_view_sql

__all__ = [
    "AdtTable",
    "FIELD_TYPES",
    "cleaning",
    "RFM_SQL",
    "rfm_view_sql",
    "__version__",
]
