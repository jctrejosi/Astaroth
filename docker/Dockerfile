# syntax=docker/dockerfile:1
# ============================================================
# Astaroth — contenedor ÚNICO (servicios de ML + Caddy interno).
#
# Variantes de build (mismo Dockerfile, se elige con --target):
#   lite (defecto) → clustering-api :8010 · XGBoost-api :8011 · uplift-api :8012
#   full           → + transformerApi :8013 · causalTransformer-api :8014 (PyTorch)
#
# Caddy escucha :8080/:8443 como usuario SIN privilegios; el compose publica
# 127.0.0.1:30380/30381 (modo edge) o 80/443 (modo directo, servidor dedicado).
# El CRM lo consume por la red compartida `shared_edge` como
# `mercaldas_astaroth_app:8080` (ruteo por prefijo: /clustering, /xgboost…).
# ============================================================

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# git: algunas dependencias se instalan desde repos GitHub
# (p. ej. causalTransformer-api: git+https://github.com/fadel/pytorch_ema.git).
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# ── Servicios ligeros (venv + código) ───────────────────────
FROM base AS clustering-build
WORKDIR /build/clustering-api
COPY clustering-api/requirements.txt .
RUN python3 -m venv /opt/clustering-venv \
    && /opt/clustering-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY clustering-api/ ./

FROM base AS xgboost-build
WORKDIR /build/xgboost-api
COPY XGBoost-api/requirements.txt .
RUN python3 -m venv /opt/xgboost-venv \
    && /opt/xgboost-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY XGBoost-api/ ./

FROM base AS uplift-build
WORKDIR /build/uplift-api
COPY uplift-api/requirements.txt .
RUN python3 -m venv /opt/uplift-venv \
    && /opt/uplift-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY uplift-api/ ./

# ── Servicios PyTorch (solo entran a la imagen con --target full) ──
# Un build --target lite NO construye estas etapas: ahorro real de disco y
# tiempo en el servidor.
FROM base AS transformer-build
WORKDIR /build/transformerApi
COPY transformerApi/requirements.txt .
RUN python3 -m venv /opt/transformer-venv \
    && /opt/transformer-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY transformerApi/ ./

FROM base AS causal-build
WORKDIR /build/causalTransformer-api
COPY causalTransformer-api/requirements.txt .
RUN python3 -m venv /opt/causal-venv \
    && /opt/causal-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY causalTransformer-api/ ./

# ── Runtime (variante lite por defecto) ─────────────────────
FROM base AS runtime
WORKDIR /app

ENV HTTP_PORT=8080 \
    HTTPS_PORT=8443 \
    XDG_DATA_HOME=/data \
    XDG_CONFIG_HOME=/config

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Caddy: proxy inverso (TLS automático y ruteo por prefijo).
ARG CADDY_VERSION=2.11.7
RUN curl -fsSL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_amd64.tar.gz" \
      | tar -xz -C /usr/local/bin caddy \
    && chmod +x /usr/local/bin/caddy

# Usuario SIN privilegios (Caddy escucha en puertos altos).
RUN groupadd --system --gid 10003 astaroth \
    && useradd --system --uid 10003 --gid astaroth --home-dir /app --shell /usr/sbin/nologin astaroth

# venvs (solo lectura) + código de los 3 servicios ligeros.
COPY --from=clustering-build /opt/clustering-venv /opt/clustering-venv
COPY --from=xgboost-build /opt/xgboost-venv /opt/xgboost-venv
COPY --from=uplift-build /opt/uplift-venv /opt/uplift-venv
COPY --chown=astaroth:astaroth --from=clustering-build /build/clustering-api ./clustering-api
COPY --chown=astaroth:astaroth --from=xgboost-build /build/xgboost-api ./xgboost-api
COPY --chown=astaroth:astaroth --from=uplift-build /build/uplift-api ./uplift-api

# Proxy y arranque (los Caddyfile usan placeholders de entorno).
COPY --chown=astaroth:astaroth docker/entrypoint.sh ./entrypoint.sh
COPY --chown=astaroth:astaroth docker/Caddyfile.http ./Caddyfile.http
COPY --chown=astaroth:astaroth docker/Caddyfile.tls ./Caddyfile.tls
# Normaliza CRLF (el repo puede clonarse en Windows), permisos y los
# directorios persistentes (certificados ACME en /data y modelos en cada
# saved_models/, que el compose monta como volúmenes).
RUN sed -i 's/\r$//' ./entrypoint.sh \
    && chmod +x ./entrypoint.sh \
    && mkdir -p /data /config \
      /app/clustering-api/saved_models \
      /app/xgboost-api/saved_models \
      /app/uplift-api/saved_models \
      /app/transformerApi/saved_models \
      /app/causalTransformer-api/saved_models \
    && chown -R astaroth:astaroth /data /config

USER astaroth

EXPOSE 8080 8443

CMD ["./entrypoint.sh"]

# ── Variante completa (+ transformer/causal, PyTorch) ───────
# Requiere RAM de sobra (~8 GB en total) y tiempo de build (torch).
# Se construye con:  docker build --target full …  (o BUILD_TARGET=full)
FROM runtime AS runtime-full
COPY --chown=astaroth:astaroth --from=transformer-build /build/transformerApi ./transformerApi
COPY --chown=astaroth:astaroth --from=causal-build /build/causalTransformer-api ./causalTransformer-api
COPY --from=transformer-build /opt/transformer-venv /opt/transformer-venv
COPY --from=causal-build /opt/causal-venv /opt/causal-venv
