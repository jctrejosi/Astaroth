-- Vista RFM por cliente (bloque de core: rfm).
-- Fuente: réplica pos.venta_lineas en la BD de analytics.
-- Excluye la anomalía del bulk (2026-05-14) igual que core.cleaning.

CREATE OR REPLACE VIEW analytics.vw_rfm_clientes AS
WITH base AS (
    SELECT
        cliente_cod,
        MAX(fecha)                    AS ultima_compra,
        MIN(fecha)                    AS primera_compra,
        COUNT(DISTINCT factura_num)   AS frecuencia,
        SUM(vlr_neto)                 AS monetario,
        SUM(vlr_neto) / NULLIF(COUNT(DISTINCT factura_num), 0) AS ticket_promedio,
        COUNT(DISTINCT tipo_producto) AS categorias_distintas
    FROM pos.venta_lineas
    WHERE fecha IS NOT NULL
      AND fecha <> DATE '2026-05-14'
    GROUP BY cliente_cod
)
SELECT
    cliente_cod,
    (DATE '2026-05-31' - ultima_compra)   AS recencia_dias,
    frecuencia,
    monetario,
    ticket_promedio,
    categorias_distintas,
    (ultima_compra - primera_compra) AS antiguedad_dias
FROM base
