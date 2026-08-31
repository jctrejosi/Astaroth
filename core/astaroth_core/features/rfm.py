"""Definición versionada de las features RFM (se materializa como vista SQL en Postgres).

La réplica `pos.venta_lineas` es la fuente; la vista agrega por cliente y
excluye la anomalía del bulk. Todos los consumidores (analytics, clustering,
XGBoost) leen la misma vista.
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
