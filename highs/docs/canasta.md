# Canasta familiar — caso de negocio sobre MIP

## Contexto comercial

El objetivo es minimizar el costo de una canasta que cumple requerimientos
mínimos por grupo de productos (nutrientes, categorías, sustitutos),
respetando stock disponible. Las decisiones son **unidades enteras por
producto**, lo que lo convierte en un MIP.

El dataset de `examples/mip_canasta.json` es un smoke test determinista, no un
modelo nutricional completo: un dataset comercial debe incorporar relaciones
reales, presentaciones, stock real y redondeos de negocio.

## Variables, objetivo y restricciones

- `x_i` (entera ≥ 0): unidades a comprar del producto `i`.
- Objetivo: `min Σ costo_i · x_i`.
- Requerimiento por grupo: `Σ_{i ∈ grupo} x_i ≥ requerido` (se pueden usar
  coeficientes por aporte si el grupo representa un nutriente).
- Presupuesto (opcional): `Σ precio_i · x_i ≤ presupuesto` como restricción.
- Stock: **cota superior por variable** (`bounds[i].upper = stock_i`) o
  restricción explícita. Si el stock no se envía, el solver no lo valida: la
  respuesta no puede afirmar que el stock se respetó.

## Construcción desde PostgreSQL

El catálogo vive en PostgreSQL (productos, precios, stock, grupos). La
construcción debe hacerse **por script**, nunca a mano:

1. Extraer con SQL solo los campos necesarios: `product_id`, `costo`,
   `stock`, `grupo`, `coeficiente_aporte`.
2. Ordenar los productos de forma estable (p. ej. por `product_id`) y usar ese
   mismo orden para `coefficients`, `integrality` y `bounds`.
3. Emitir el JSON del request y enviarlo a `POST /v1/mip/solve`.
4. Registrar el mapeo posición → `product_id` usado al construir el modelo.

Pseudo-SQL de referencia:

```sql
SELECT p.id, p.costo, COALESCE(s.stock, 0) AS stock, g.grupo, g.aporte
FROM productos p
JOIN stock s ON s.producto_id = p.id
JOIN grupo_aportes g ON g.producto_id = p.id
WHERE p.activo AND s.stock > 0
ORDER BY p.id, g.grupo;
```

Con ese resultado se agrupan los aportes por grupo y se arma una restricción
`>= requerido_grupo` por grupo.

## Política de unidades, precios, inventario y redondeo

- **Unidades**: `x_i` son unidades enteras del producto (o multipacks si el
  negocio los define así). El solver no conoce presentaciones: la conversión es
  responsabilidad del cliente.
- **Precios**: usar la misma unidad monetaria y la misma escala para todos los
  productos (en el ejemplo, pesos colombianos enteros: `12000`). No mezclar
  pesos y centavos entre productos.
- **Inventario**: el stock se codifica como cota superior; un producto sin
  stock debe excluirse del modelo o llevar `upper: 0`.
- **Redondeo**: el contrato no redondea nada; si el negocio exige redondear
  cantidades o precios, hazlo antes de enviar el modelo y documenta la regla.
  Las tolerancias numéricas internas no sustituyen una política de negocio.

## Ejemplo end-to-end

Request de referencia (extracto de `examples/mip_canasta.json`):

```json
{
  "objective": { "sense": "minimize",
    "coefficients": [12000, 18000, 4000, 3000, 5000, 4500] },
  "constraints": [
    { "coefficients": [1, 1, 0, 0, 0, 0], "sense": ">=", "rhs": 5 },
    { "coefficients": [0, 0, 1, 1, 0, 0], "sense": ">=", "rhs": 4 },
    { "coefficients": [0, 0, 0, 0, 1, 0], "sense": ">=", "rhs": 6 },
    { "coefficients": [0, 0, 0, 0, 0, 1], "sense": ">=", "rhs": 3 }
  ],
  "integrality": ["integer", "integer", "integer", "integer", "integer", "integer"]
}
```

```bash
curl -X POST http://127.0.0.1:8000/v1/mip/solve \
  -H "Content-Type: application/json" --data-binary @examples/mip_canasta.json
```

Resultado: `status: "optimal"`, `objective_value: 115500`, variables
`[5, 0, 0, 4, 6, 3]` (el producto más barato de cada grupo). Con stock
`[3, 4, 6, 5, 10, 4]` codificado como cotas superiores, el óptimo determinista
es `127500` y el solver reparte el primer grupo entre los dos productos.

## Interpretación del resultado

- `optimal`: el costo mínimo probado. `message` es `null`.
- `time_limit` (u otro límite): puede venir la mejor canasta encontrada; el
  `message` aclara que no se probó optimalidad y `gap` (si existe) acota la
  distancia al óptimo.
- `infeasible`: los requerimientos no son alcanzables con el stock/cotas
  dados; suele indicar demanda mal parametrizada, no un fallo del servicio.

## Validación posterior de factibilidad y objetivo

Nunca confíes solo en `status`: valida en el cliente antes de usar la compra.

1. Recalcular `Σ costo_i · x_i` y compararlo con `objective_value`.
2. Verificar cada requerimiento de grupo con las variables devueltas.
3. Verificar `0 ≤ x_i ≤ stock_i` para cada producto (si el stock se envió).
4. Verificar integralidad dentro de tolerancia (`|x_i − round(x_i)| ≤ 1e-6`).
5. Si el estado no es `optimal`, no presentar el resultado como óptimo ante el
   negocio.

Estos pasos son los que ejecuta `tests/e2e/test_canasta.py`, que funciona como
referencia ejecutable de la validación.
