#!/usr/bin/env bash
# ============================================================
# Despliegue de Astaroth (6 APIs de ML en un contenedor) desde `dev`.
#
# Uso:
#   bash deploy/deploy.sh                 # despliega origin/dev
#   bash deploy/deploy.sh <sha|ref>       # despliega un commit/ref concreto
#   DEPLOY_PATH=/ruta bash deploy/deploy.sh
#
# Requiere el `.env` del servidor (ADMIN_KEY, API_KEYS, DATABASE_URL), que no
# se versiona. Si existe `docker-compose.edge.yml` se usa además del base.
# ============================================================
set -Eeuo pipefail

ROOT="${DEPLOY_PATH:-/mnt/c/Users/Desarrolo4/Documents/astaroth}"
TARGET="${1:-origin/dev}"

log()  { printf '[astaroth-deploy] %s\n' "$*"; }
warn() { printf '[astaroth-deploy] AVISO: %s\n' "$*" >&2; }
die()  { printf '[astaroth-deploy] ERROR: %s\n' "$*" >&2; exit 1; }

cd "$ROOT" 2>/dev/null || die "No existe DEPLOY_PATH=$ROOT"
[[ -f docker-compose.yml ]] || die "Falta docker-compose.yml"
[[ -f .env ]] || die "Falta $ROOT/.env (ADMIN_KEY, API_KEYS, DATABASE_URL)"
command -v git    >/dev/null || die "git no está instalado"
command -v docker >/dev/null || die "docker no está en PATH"
docker info >/dev/null 2>&1 || die "Docker no responde (revisa systemctl status docker)"

GIT_SSH_KEY="${GIT_SSH_KEY:-/etc/mercaldas/deploy_key}"
if [[ -r "$GIT_SSH_KEY" ]]; then
  export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh -i $GIT_SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new}"
fi

git_here() {
  git -c safe.directory="$ROOT" -c core.hooksPath=/nonexistent -C "$ROOT" "$@"
}

log "Repositorio: $ROOT"
log "Objetivo   : $TARGET"

git_here fetch --prune origin '+refs/heads/dev:refs/remotes/origin/dev'
git_here rev-parse --verify --quiet "$TARGET^{commit}" >/dev/null \
  || die "El commit/ref '$TARGET' no existe tras el fetch"

git_here checkout -f -B dev "$TARGET"
COMMIT="$(git_here rev-parse --short=12 HEAD)"
log "Checkout en dev: $COMMIT — $(git_here log -1 --pretty=%s)"

COMPOSE=(docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml")
if [[ -f "$ROOT/docker-compose.edge.yml" ]]; then
  COMPOSE+=(-f "$ROOT/docker-compose.edge.yml")
else
  warn "Sin docker-compose.edge.yml: el servicio no quedará en la red shared_edge."
fi

"${COMPOSE[@]}" config --quiet || die "docker compose config falló"

log "Construyendo imagen astaroth:local (puede tardar varios minutos)…"
"${COMPOSE[@]}" build

log "Recreando contenedor…"
"${COMPOSE[@]}" up -d --pull never

log "Esperando healthcheck de astaroth…"
STATUS=""
for _ in $(seq 1 120); do
  STATUS="$(docker inspect -f \
    '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
    astaroth 2>/dev/null || true)"
  case "$STATUS" in
    healthy) break ;;
    unhealthy|exited|dead)
      docker logs --tail 120 astaroth 2>&1 || true
      die "astaroth quedó en estado '$STATUS'"
      ;;
  esac
  sleep 5
done

if [[ "$STATUS" != "healthy" ]]; then
  docker logs --tail 120 astaroth 2>&1 || true
  die "Timeout esperando astaroth healthy (último: '${STATUS:-desconocido}')"
fi

"${COMPOSE[@]}" ps
log "Despliegue completado: $COMMIT"
