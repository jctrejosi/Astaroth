# Despliegue de Astaroth en el VPS (contenedor único)

Guía del servidor para el contenedor de ML (`docker/`). Complementa a
`docs/SECURITY.md` (modelo de seguridad) y al README de `docker/`.

Astaroth **no se expone a internet por defecto**: lo consume el CRM por la red
interna `shared_edge`. Este documento cubre también cómo exponerlo si algún día
se decide (opt-in).

---

## 1. Requisitos en el servidor

- Docker + compose (en Windows Server, vía WSL2 — ver
  `ecommerce/docs/DESPLIEGUE-DOCKER.md` §2, mismo procedimiento).
- **Ecommerce y/o CRM ya desplegados** (crean la red `shared_edge`; si no, este
  compose también la crea, pero el CRM no podrá alcanzarlo hasta estar arriba).
- RAM: variante `lite` ~2 GB; `full` (PyTorch) ~8 GB en total.
- Firewall: **solo 80/443** abiertos (los publica el edge). Astaroth no abre
  puertos propios fuera de loopback.

## 2. Puesta en marcha

```bash
# En el repo Astaroth (raíz)
cp docker/.env.example docker/.env
node scripts-agent/set-prod-secrets.mjs    # genera ADMIN_KEY

node prod.js --dns                         # lee qué configurar (DNS/red)
node prod.js                               # sincroniza .env, construye y levanta
```

`prod.js` lee `prod.config.json` (`mode: edge|direct`, dominio, puertos,
`withPyTorch`) y sincroniza `docker/.env` **sin pisar secretos**.

### Puertos publicados

| Contenedor | Publicados | Notas |
|---|---|---|
| `mercaldas_astaroth_app` | `127.0.0.1:30380` / `30381` | solo loopback; lo alcanza el edge por `shared_edge` |
| (edge) `edge_caddy` | `80` / `443` | único punto de entrada |

## 3. DNS

- **Uso interno normal (CRM)**: no hace falta DNS ni exposición. El CRM llama a
  `http://mercaldas_astaroth_app:8080/clustering|/xgboost|/uplift`.
- **Exponer `ml.mercaldas.jcti.xyz` (opt-in)**:
  1. Crea el registro `A` `ml.mercaldas` → IP del servidor (TTL 600).
  2. Descomenta el bloque `ml.mercaldas.jcti.xyz` en
     `ecommerce/docker/edge/Caddyfile`.
  3. `cd ecommerce/docker/edge && docker compose up -d` (Caddy recarga y emite
     el certificado).
  4. Revisa `docs/SECURITY.md` (superficie sensible) antes de hacerlo.

## 4. Sincronizar la `ADMIN_KEY` con el CRM

La clave de Astaroth y la del CRM son **la misma**:

| Astaroth (`docker/.env`) | CRM (`docker/.env`) |
|---|---|
| `ADMIN_KEY` | `CLUSTERING_API_KEY` |

`node scripts-agent/set-prod-secrets.mjs` imprime la clave generada: cópiala al
`CLUSTERING_API_KEY` del CRM si difieren y reinicia ambos contenedores.

## 5. Base de analytics (opcional)

Los endpoints `/fit-from-db` y `/assign-from-db` leen
`analytics.vw_rfm_clientes` de la réplica analytics del CRM. Para habilitarlos,
con el CRM levantado:

```bash
docker network connect crm_internal mercaldas_astaroth_app
# DATABASE_URL=postgresql://postgres:postgres@analytics-postgres:5432/analytics  (docker/.env)
```

Sin esa red, esos dos endpoints fallan; el resto de la API funciona igual.

## 6. Verificación

```bash
docker port mercaldas_astaroth_app     # espera 127.0.0.1:30380/30381 (nada en 0.0.0.0)
docker compose -f docker/docker-compose.yml ps

# Salud (desde el propio host)
curl -fsS http://127.0.0.1:30380/clustering/health

# Desde el CRM (contenedor):
docker exec mercaldas_crm_app curl -fsS http://mercaldas_astaroth_app:8080/clustering/health

# Desde fuera: el puerto loopback NO debe responder
curl -sS -m 3 http://<IP_DEL_SERVIDOR>:30380/ || echo "OK: 30380 cerrado"
```

Y en el CRM: `docker exec mercaldas_crm_app printenv CLUSTERING_API_URL`.

## 7. Operación

```bash
node prod.js                      # reconstruye (si cambió el código) y levanta
node prod.js --no-build           # reinicia sin reconstruir
node prod.js --status | --logs | --stop
```

- Cambiar dominio/puertos/variante: edita `prod.config.json` y `node prod.js`.
- `withPyTorch: true` reconstruye con `--target full` (tarda: instala torch) y
  arranca los servicios 8013/8014.
- Los modelos persisten en volúmenes (`astaroth_models_*`).

## 8. Problemas típicos

| Síntoma | Causa / solución |
|---|---|
| El contenedor no arranca y el log dice `ADMIN_KEY` | Falta generarla: `node scripts-agent/set-prod-secrets.mjs` y `node prod.js`. |
| El CRM responde 500/502 al usar ML | Astaroth no está arriba o no comparten `shared_edge` (`docker network inspect shared_edge`). |
| `/fit-from-db` responde 503 | No conectaste `crm_internal` o `DATABASE_URL` no apunta a `analytics-postgres`. |
| `ASTROTH_FULL=1` y no arrancan 8013/8014 | La imagen es `lite`: pon `"withPyTorch": true` y `node prod.js`. |
| Build lentísimo / sin disco | Es la variante `full` (torch). Usa `lite` si no usas transformer/causal. |
| 502 en `ml.…` a través del edge | El bloque del dominio no está descomentado en el Caddyfile del edge o el contenedor está abajo. |
