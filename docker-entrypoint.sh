#!/usr/bin/env bash
# Arranca los procesos del contenedor de Astaroth:
#   1. clustering-api       → ${ASTROTH_HOST}:8010
#   2. xgboost-api          → ${ASTROTH_HOST}:8011
#   3. uplift-api           → ${ASTROTH_HOST}:8012
#   4. transformerApi       → ${ASTROTH_HOST}:8013 (PyTorch) — con ASTROTH_FULL=1
#   5. causalTransformer-api → ${ASTROTH_HOST}:8014 (PyTorch) — con ASTROTH_FULL=1
#   6. highs (LP/MIP/QP)    → ${ASTROTH_HOST}:8015 (ligero, siempre activo)
#   7. Caddy (proxy)        → $PORT (público) — con ASTROTH_PROXY=1
#
# Variables:
#   ASTROTH_HOST   host de escucha de los uvicorn (por defecto 0.0.0.0, para que
#                  los puertos sean accesibles desde fuera del contenedor).
#   ASTROTH_PROXY  1 (defecto) = arranca Caddy y enruta por prefijo en $PORT
#                  (modo Render). 0 = solo los puertos directos.
#   ASTROTH_FULL   1 = arranca también los PyTorch (8013/8014). Consumen ~2 GB
#                  de RAM cada uno; no hacen falta para el flujo de campañas.
set -euo pipefail

HOST="${ASTROTH_HOST:-0.0.0.0}"
PUBLIC_PORT="${PORT:-10000}"
PROXY="${ASTROTH_PROXY:-1}"

echo "==> Astaroth: uvicorn en ${HOST}:8010/8011/8012/8015${ASTROTH_FULL:+ (+8013/8014)}  · proxy=${PROXY}"

start() {
  local name="$1" dir="$2" venv="$3" entry="$4" port="$5"
  cd "/app/$dir"
  echo "==> $name: uvicorn en ${HOST}:$port"
  "/opt/$venv/bin/uvicorn" "$entry" --host "$HOST" --port "$port" &
}

start clustering-api        clustering-api        clustering-venv app.main:app     8010
start xgboost-api           xgboost-api           xgboost-venv    app.main:app     8011
start uplift-api            uplift-api            uplift-venv     app.main:app     8012
start highs                 highs                 highs-venv      highs_api.main:app 8015

if [[ "${ASTROTH_FULL:-0}" == "1" ]]; then
  start transformerApi         transformerApi         transformer-venv apis.main:app 8013
  start causalTransformer-api  causalTransformer-api  causal-venv      api.main:app   8014
fi

cd /app

# Si cualquiera muere, se detiene todo (Render reinicia el servicio).
trap 'jobs -p | xargs -r kill 2>/dev/null || true' INT TERM EXIT

if [[ "$PROXY" == "1" ]]; then
  echo "==> caddy: proxy por prefijo en :${PUBLIC_PORT}"
  HTTP_PORT="$PUBLIC_PORT" caddy run --config /app/Caddyfile --adapter caddyfile &
fi

wait -n
