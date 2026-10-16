# `docker/` — despliegue en un contenedor único

Imagen única con **los servicios de ML + Caddy interno**, pensada para el VPS
de Mercaldas. En el servidor NO publica puertos a internet: escucha en
`127.0.0.1:30380/30381` y el **edge compartido** (`ecommerce/docker/edge/`) es
el único que publica `80/443` y hace TLS (queda detrás de `ml.mercaldas.jcti.xyz`
si algún día se expone).

| Proceso | Puerto (interno) | Publicado | Internet |
|---|---|---|---|
| clustering-api | `127.0.0.1:8010` | ❌ | ❌ (red interna) |
| XGBoost-api | `127.0.0.1:8011` | ❌ | ❌ (red interna) |
| uplift-api | `127.0.0.1:8012` | ❌ | ❌ (red interna) |
| transformerApi | `127.0.0.1:8013` | ❌ | ❌ (solo variante `full`) |
| causalTransformer-api | `127.0.0.1:8014` | ❌ | ❌ (solo variante `full`) |
| Caddy (proxy) | `:8080` / `:8443` | `127.0.0.1:30380` / `30381` | ❌ (lo alcanza el edge) |
| **Edge compartido** (`ecommerce/docker/edge/`) | `:80` / `:443` | `80` / `443` | ✅ **único** |

Puertos propios (nada «genérico» que choque con IIS u otros servicios):
ecommerce `30180/30181`, CRM `30280/30281`, Astaroth `30380/30381`.

El CRM lo consume por la red `shared_edge` como `mercaldas_astaroth_app:8080`
(`/clustering`, `/xgboost`, `/uplift`).

📖 **Guías**: [`docs/DESPLIEGUE-DOCKER.md`](../docs/DESPLIEGUE-DOCKER.md)
(pasos del servidor, firewall y DNS) · [`docs/SECURITY.md`](../docs/SECURITY.md).

## Rápido

```bash
cp docker/.env.example docker/.env
node scripts-agent/set-prod-secrets.mjs   # genera ADMIN_KEY (fail-closed)
node prod.js                              # sincroniza .env, construye y levanta

node prod.js --dns                        # qué configurar en DNS/red
node prod.js --status | --logs | --stop
```

> **Solo con Docker (sin node)**: `cp docker/.env.example docker/.env`, define la
> `ADMIN_KEY` (o genérala con el script) y luego
> `docker compose -f docker/docker-compose.yml build && docker compose -f docker/docker-compose.yml up -d`.
> `BUILD_TARGET` en `docker/.env` elige `lite`/`full`. `prod.js` solo añade el
> sincronizado de dominio/puertos desde `prod.config.json` y la validación.

Modos (en `prod.config.json`):

- `"mode": "edge"` (recomendado): TLS lo termina el edge; el contenedor queda en
  loopback `30380/30381` (`TLS=false` + `ALLOW_INSECURE=true` en `docker/.env`).
- `"mode": "direct"` (servidor dedicado): este contenedor publica `80/443` y
  emite el TLS de `HOST_ML` él mismo.

Variantes de imagen (`"withPyTorch"` en la config):

| Variante | Servicios | RAM orientativa |
|---|---|---|
| `lite` (defecto) | clustering + xgboost + uplift | ~2 GB |
| `full` | + transformer + causal (PyTorch) | ~8 GB |

> `full` instala torch en dos venvs: el build tarda bastante más. `ASTROTH_FULL`
> decide si los servicios PyTorch **arrancan** dentro del contenedor (por
> defecto no, aunque la imagen los contenga).

## Archivos

| Archivo | Rol |
|---|---|
| `Dockerfile` | Multi-stage: 5 venvs + Caddy 2.11.7 → runtime `lite`/`full`, usuario sin privilegios. |
| `entrypoint.sh` | Fail-closed (ADMIN_KEY/TLS), arranca uvicorn en `127.0.0.1` y Caddy. |
| `Caddyfile.http` | Modo edge: HTTP en `:8080`, ruteo por prefijo. |
| `Caddyfile.tls` | Modo directo: HTTPS Let's Encrypt para `HOST_ML`. |
| `docker-compose.yml` | Un servicio, redes `edge`+`shared_edge`, volúmenes de modelos, `cap_drop`, healthcheck. |
| `.env.example` | Dominio, TLS, puertos, `ADMIN_KEY` y BD de analytics. |

## Seguridad (resumen)

- Sin exposición pública por defecto: solo loopback + redes Docker privadas.
- **`ADMIN_KEY` obligatoria** (header `X-Admin-Key`): el contenedor NO arranca si
  falta o sigue en `change-me`. **Compartida con el CRM** (`CLUSTERING_API_KEY`).
- `TLS=false` exige `ALLOW_INSECURE=true` (modo edge, aceptado a conciencia).
- Contenedor sin root, `cap_drop: ALL`, `no-new-privileges`, logs con rotación,
  límite de cuerpo HTTP (`MAX_REQUEST_BODY`) y cabeceras `nosniff`/sin `Server`.
- Modelos en volúmenes con nombre (persisten entre reconstrucciones).

> Exponer `ml.mercaldas.jcti.xyz` es **opt-in** (bloque comentado en el Caddyfile
> del edge). Antes de hacerlo, lee `docs/SECURITY.md`.
