# Seguridad — Astaroth (despliegue en contenedor)

Modelo de seguridad del contenedor de ML (`docker/`) en el VPS de Mercaldas.
Complementa a `docs/DESPLIEGUE-DOCKER.md` (operación) y al README de `docker/`.

## Modelo de exposición (por defecto: NO público)

```
Internet ──> edge compartido (80/443, TLS) ──> solo si se descomenta ml.…
                                              │
CRM (mercaldas_crm_app) ── shared_edge ──────>│──> mercaldas_astaroth_app:8080
                                              │      └─ Caddy → 127.0.0.1:8010-8014
                                              └─ (red Docker privada, sin ruta a internet)
```

- El contenedor publica sus puertos SOLO en `127.0.0.1:30380/30381` (loopback del
  host): no accesible desde internet ni desde la red local.
- Los 5 servicios escuchan en `127.0.0.1` **dentro** del contenedor; solo Caddy
  habla con ellos.
- El consumidor real es el **CRM**, por la red `shared_edge`
  (`http://mercaldas_astaroth_app:8080/clustering|/xgboost|/uplift`). No necesita
  exposición pública.
- Exponer `ml.mercaldas.jcti.xyz` en el edge es **opt-in** y está desaconsejado
  salvo necesidad: los endpoints de ML son costosos (CPU/RAM) y una superficie
  de abuso/DoS aunque estén protegidos.

## Autenticación

- Los endpoints sensibles (`/admin/*`, `/fit*`, `/assign*`, segmentación…) exigen
  el header `X-Admin-Key` = `ADMIN_KEY`.
- **Fail-closed**: el entrypoint NO arranca si `ADMIN_KEY` está vacía o en
  `change-me` (salvo `ALLOW_INSECURE=true` explícito, pensado para pruebas).
- `ADMIN_KEY` **se comparte con el CRM**: su backend la envía como
  `CLUSTERING_API_KEY`. Deben coincidir exactamente; al rotarla, actualiza ambas
  y reinicia los dos contenedores. Generación: `node scripts-agent/set-prod-secrets.mjs`.
- Algunos endpoints (p. ej. predicciones de xgboost/uplift) no piden clave: por
  eso la exposición pública se considera opt-in y se apoya primero en el
  aislamiento de red.

## Aislamiento y endurecimiento del contenedor

- `cap_drop: ALL` + `no-new-privileges`: sin capacidades extra ni escalada.
- Proceso como usuario **sin privilegios** (`astaroth`, sin shell de login);
  Caddy escucha en `8080/8443` (no root).
- Redes: `astaroth_edge` (salida) y `shared_edge` (privada, compartida con el
  CRM/edge). La base de analytics (si se conecta `crm_internal`) es una red
  interna sin ruta a internet.
- Solo se publican puertos de loopback; el firewall del VPS abre **únicamente
  80/443** (del edge).

## Límites y superficie

- `MAX_REQUEST_BODY` (def. 100 MB) acota el cuerpo de las peticiones en Caddy:
  los `/fit` reciben datasets JSON y sin límite serían un vector de abuso.
- `encode zstd gzip` + `X-Content-Type-Options: nosniff`; se elimina `Server`.
- Logs de Docker con rotación (`10m × 5`) para no llenar el disco.
- Sin endpoints de administración de Caddy (`admin off`).
- Los modelos (`saved_models/`) viven en volúmenes con nombre: sobreviven a
  reconstrucciones y no van dentro de la imagen.

## TLS

- Modo edge (recomendado): el TLS lo termina el edge compartido; el tráfico
  interno va en claro **solo** dentro de redes Docker privadas.
- Modo directo: Caddy emite Let's Encrypt para `HOST_ML` (validación HTTP-01 en
  el puerto 80) y sirve HSTS. Exige `HOST_ML` y `ACME_EMAIL`.
- `TLS=false` requiere `ALLOW_INSECURE=true` (evita servir el API en claro por
  descuido).

## Secretos y datos

- `docker/.env` (permisos `600`, gitignored): `ADMIN_KEY`, `DATABASE_URL`.
- `DATABASE_URL` apunta a la réplica **analytics** (`analytics-postgres`, red
  `crm_internal`), no a la BD transaccional. Si se omite, los endpoints
  `/fit-from-db` y `/assign-from-db` fallan y el resto funciona igual.
- La imagen no contiene `.env` ni `saved_models/` (excluidos por `.dockerignore`).

## Checklist antes de exponer (si algún día se hace)

- [ ] `ADMIN_KEY` fuerte y sincronizada con el CRM.
- [ ] `MAX_REQUEST_BODY` ajustado a lo que realmente se envía.
- [ ] Secretos rotados tras cualquier copia/traslado del `.env`.
- [ ] Valorar además Basic Auth en el bloque del edge para `ml.…` y limitar
      el origen por firewall si solo lo consume un socio.
