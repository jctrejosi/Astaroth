#!/usr/bin/env bash
# Arranca los procesos del contenedor de Astaroth:
#   1. clustering-api       → 127.0.0.1:8010 (interno)
#   2. xgboost-api          → 127.0.0.1:8011 (interno)
#   3. uplift-api           → 127.0.0.1:8012 (interno)
#   4. transformerApi       → 127.0.0.1:8013 (interno, PyTorch) — opcional
#   5. causalTransformer-api → 127.0.0.1:8014 (interno, PyTorch) — opcional
#   6. Caddy (proxy)        → $PORT (público, el que inyecta Render)
#
# Los servicios PyTorch (8013/8014) consumen ~2 GB de RAM cada uno; por
# defecto NO se arrancan (el flujo de campañas solo usa clustering/xgboost/
# uplift). Para incluirlos define ASTROTH_FULL=1 y usa un plan con ≥4 GB.
set -euo pipefail

PUBLIC_PORT="${PORT:-10000}"

echo "==> Astaroth: proxy :${PUBLIC_PORT} → clustering:8010, xgboost:8011, uplift:8012${ASTROTH_FULL:+ , transformer:8013, causal:8014}"

start() {
  local name="$1" dir="$2" venv="$3" entry="$4" port="$5"
  cd "/app/$dir"
  echo "==> $name: uvicorn en 127.0.0.1:$port"
  "/opt/$venv/bin/uvicorn" "$entry" --host 127.0.0.1 --port "$port" &
}

start clustering-api        clustering-api        clustering-venv app.main:app     8010
start xgboost-api           xgboost-api           xgboost-venv    app.main:app     8011
start uplift-api            uplift-api            uplift-venv     app.main:app     8012

if [[ "${ASTROTH_FULL:-0}" == "1" ]]; then
  start transformerApi         transformerApi         transformer-venv apis.main:app 8013
  start causalTransformer-api  causalTransformer-api  causal-venv      api.main:app   8014
fi

cd /app
echo "==> caddy: proxy en :${PUBLIC_PORT}"
HTTP_PORT="$PUBLIC_PORT" caddy run --config /app/Caddyfile --adapter caddyfile &
CADDY_PID=$!

# Si cualquiera muere, se detiene todo (Render reinicia el servicio).
trap 'jobs -p | xargs -r kill 2>/dev/null || true' INT TERM EXIT

wait -n
