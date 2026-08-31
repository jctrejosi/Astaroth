"""Definición versionada del RFM (bloque de core).

El RFM es una feature engineering por cliente: recencia, frecuencia y
monetario (más ticket promedio, categorías y antigüedad), calculada sobre la
réplica `pos.venta_lineas` y excluyendo el bulk anómalo (2026-05-14).

Se materializa como vista SQL en la BD de analytics. El pipeline de
segmentación la lee y envía las columnas numéricas a `clustering-api`.
"""

RFM_SQL = """
CREATE OR REPLACE VIEW {view} AS
WITH base AS (
    SELECT
        cliente_cod,
        MAX(fecha)                    AS ultima_compra,
        MIN(fecha)                    AS primera_compra,
        COUNT(DISTINCT factura_num)   AS frecuencia,
        SUM(vlr_neto)                 AS monetario,
        SUM(vlr_neto) / NULLIF(COUNT(DISTINCT factura_num), 0) AS ticket_promedio,
        COUNT(DISTINCT tipo_producto) AS categorias_distintas
    FROM {tabla}
    WHERE fecha IS NOT NULL
      AND fecha <> DATE '2026-05-14'
    GROUP BY cliente_cod
)
SELECT
    cliente_cod,
    (DATE '{ref}' - ultima_compra)   AS recencia_dias,
    frecuencia,
    monetario,
    ticket_promedio,
    categorias_distintas,
    (ultima_compra - primera_compra) AS antiguedad_dias
FROM base
"""


def rfm_view_sql(
    view: str = "analytics.vw_rfm_clientes",
    tabla: str = "pos.venta_lineas",
    ref: str = "2026-05-31",
) -> str:
    """Devuelve el DDL de la vista RFM, parametrizado."""
    return RFM_SQL.format(view=view, tabla=tabla, ref=ref)
