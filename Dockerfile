# syntax=docker/dockerfile:1

# ============================================================
# Astaroth — un solo contenedor con los 3 servicios de ML + Caddy
#   clustering-api :8010  ·  xgboost-api :8011  ·  uplift-api :8012
# Caddy expone un solo puerto público y rutea por prefijo.
# ============================================================

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ---- Etapa 1: clustering-api ----
FROM base AS clustering-build
WORKDIR /build/clustering-api
COPY clustering-api/requirements.txt .
RUN python3 -m venv /opt/clustering-venv \
    && /opt/clustering-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY clustering-api/ ./

# ---- Etapa 2: XGBoost-api ----
FROM base AS xgboost-build
WORKDIR /build/xgboost-api
COPY XGBoost-api/requirements.txt .
RUN python3 -m venv /opt/xgboost-venv \
    && /opt/xgboost-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY XGBoost-api/ ./

# ---- Etapa 3: uplift-api ----
FROM base AS uplift-build
WORKDIR /build/uplift-api
COPY uplift-api/requirements.txt .
RUN python3 -m venv /opt/uplift-venv \
    && /opt/uplift-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY uplift-api/ ./

# ---- Etapa 4: transformerApi (iTransformer, PyTorch) ----
FROM base AS transformer-build
WORKDIR /build/transformerApi
COPY transformerApi/requirements.txt .
RUN python3 -m venv /opt/transformer-venv \
    && /opt/transformer-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY transformerApi/ ./

# ---- Etapa 5: causalTransformer-api (PyTorch) ----
FROM base AS causal-build
WORKDIR /build/causalTransformer-api
COPY causalTransformer-api/requirements.txt .
RUN python3 -m venv /opt/causal-venv \
    && /opt/causal-venv/bin/pip install --no-cache-dir -r requirements.txt
COPY causalTransformer-api/ ./

# ---- Runtime ----
FROM base

WORKDIR /app

# Python + curl para descargar Caddy
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Caddy: reverse proxy
ARG CADDY_VERSION=2.9.1
RUN curl -fsSL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_amd64.tar.gz" \
    | tar -xz -C /usr/local/bin caddy \
    && chmod +x /usr/local/bin/caddy

# Venvs + código de los 5 servicios
COPY --from=clustering-build /opt/clustering-venv /opt/clustering-venv
COPY --from=xgboost-build /opt/xgboost-venv /opt/xgboost-venv
COPY --from=uplift-build /opt/uplift-venv /opt/uplift-venv
COPY --from=transformer-build /opt/transformer-venv /opt/transformer-venv
COPY --from=causal-build /opt/causal-venv /opt/causal-venv

COPY --from=clustering-build /build/clustering-api ./clustering-api
COPY --from=xgboost-build /build/xgboost-api ./xgboost-api
COPY --from=uplift-build /build/uplift-api ./uplift-api
COPY --from=transformer-build /build/transformerApi ./transformerApi
COPY --from=causal-build /build/causalTransformer-api ./causalTransformer-api

# Proxy y arranque
COPY Caddyfile ./Caddyfile
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

EXPOSE 10000

CMD ["./docker-entrypoint.sh"]
