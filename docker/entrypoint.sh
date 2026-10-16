#!/usr/bin/env bash
# Arranque del contenedor de Astaroth:
#   1. clustering-api        → 127.0.0.1:8010 (interno)
#   2. xgboost-api           → 127.0.0.1:8011 (interno)
#   3. uplift-api            → 127.0.0.1:8012 (interno)
#   4. transformerApi        → 127.0.0.1:8013 (interno, PyTorch — solo ASTROTH_FULL=1)
#   5. causalTransformer-api → 127.0.0.1:8014 (interno, PyTorch — solo ASTROTH_FULL=1)
#   6. Caddy (proxy)         → :${HTTP_PORT}/:${HTTPS_PORT} (el compose publica
#                              127.0.0.1:30380/30381 o 80/443 en modo directo)
#
# El Caddyfile se elige por TLS: con TLS=true (directo) se sirve HTTPS con
# Let's Encrypt para HOST_ML; con TLS=false (detrás del edge compartido) se
# sirve HTTP en :8080 para cualquier Host.
set -euo pipefail

HTTP_PORT="${HTTP_PORT:-8080}"
HTTPS_PORT="${HTTPS_PORT:-8443}"
export HTTP_PORT HTTPS_PORT
MAX_REQUEST_BODY="${MAX_REQUEST_BODY:-100MB}"
export MAX_REQUEST_BODY

# ── Salvaguardas de seguridad (fail-closed) ─────────────────

# TLS=false publica el API sin cifrar (datos y X-Admin-Key en claro): hay que
# aceptarlo explícitamente (modo edge: el TLS lo termina el edge por delante).
TLS="${TLS:-true}"
if [ "$TLS" = "false" ] && [ "${ALLOW_INSECURE:-false}" != "true" ]; then
  echo "✘ TLS=false sirve el API SIN cifrar. Si es a propósito (edge por delante)," >&2
  echo "  arranca con ALLOW_INSECURE=true." >&2
  exit 1
fi

# La X-Admin-Key protege /admin/*, /fit*, /assign*…: sin ella quedarían
# abiertos a cualquiera que alcance el contenedor.
ADMIN_KEY="${ADMIN_KEY:-}"
if [ -z "$ADMIN_KEY" ] || [ "$ADMIN_KEY" = "change-me" ]; then
  if [ "${ALLOW_INSECURE:-false}" != "true" ]; then
    echo "✘ ADMIN_KEY vacía o 'change-me' (los endpoints de entrenamiento/admin" >&2
    echo "  quedarían sin protección). Generala con:" >&2
    echo "    node scripts-agent/set-prod-secrets.mjs   (en el repo)" >&2
    exit 1
  fi
  echo "⚠️  ADMIN_KEY débil/ausente (ALLOW_INSECURE=true): NO usar así en producción." >&2
fi
export ADMIN_KEY

# ── Caddyfile según modo ────────────────────────────────────
if [ "$TLS" = "false" ]; then
  CADDYFILE=/app/Caddyfile.http
else
  if [ -z "${HOST_ML:-}" ] || [ -z "${ACME_EMAIL:-}" ]; then
    echo "✘ Modo TLS directo: define HOST_ML y ACME_EMAIL (o usa el modo edge:" >&2
    echo "  TLS=false + ALLOW_INSECURE=true con el edge compartido por delante)." >&2
    exit 1
  fi
  CADDYFILE=/app/Caddyfile.tls
fi

echo "==> Astaroth (contenedor único): Caddy :${HTTP_PORT}/:${HTTPS_PORT} · MAX_REQUEST_BODY=${MAX_REQUEST_BODY}${ASTROTH_FULL:+ · ASTROTH_FULL=${ASTROTH_FULL}}"

# ── Servicios ML (uvicorn en 127.0.0.1) ─────────────────────
start() {
  local name="$1" dir="$2" venv="$3" entry="$4" port="$5"
  echo "==> $name: uvicorn en 127.0.0.1:$port"
  ( cd "/app/$dir" && exec "/opt/$venv/bin/uvicorn" "$entry" \
      --host 127.0.0.1 --port "$port" ) &
}

start clustering-api        clustering-api        clustering-venv app.main:app 8010
start xgboost-api           XGBoost-api           xgboost-venv    app.main:app 8011
start uplift-api            uplift-api            uplift-venv     app.main:app 8012

if [ "${ASTROTH_FULL:-0}" = "1" ]; then
  if [ -x /opt/transformer-venv/bin/uvicorn ] && [ -x /opt/causal-venv/bin/uvicorn ]; then
    start transformerApi         transformerApi         transformer-venv apis.main:app 8013
    start causalTransformer-api  causalTransformer-api  causal-venv      api.main:app  8014
  else
    echo "⚠️  ASTROTH_FULL=1 pero esta imagen es 'lite' (sin venvs PyTorch)." >&2
    echo "  Reconstruye con BUILD_TARGET=full (p. ej. `node prod.js` con" >&2
    echo "  \"withPyTorch\": true en prod.config.json)." >&2
  fi
fi

# ── Caddy (proxy) ───────────────────────────────────────────
echo "==> caddy: ${CADDYFILE}"
caddy run --config "$CADDYFILE" --adapter caddyfile &
CADDY_PID=$!

# Si cualquiera muere, se detiene todo (el orquestador reinicia el contenedor).
trap 'kill 0 2>/dev/null || true' INT TERM EXIT

wait -n
