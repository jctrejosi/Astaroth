# syntax=docker/dockerfile:1

# ============================================================
# Astaroth — un solo contenedor con los servicios de ML + optimización + Caddy
#   clustering-api :8010  ·  xgboost-api :8011  ·  uplift-api :8012
#   transformerApi :8013  ·  causalTransformer-api :8014  ·  highs :8015
# Caddy expone un solo puerto público y rutea por prefijo.
# ============================================================

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# git: hay dependencias que pip instala desde repositorios GitHub
# (p. ej. causalTransformer-api: git+https://github.com/fadel/pytorch_ema.git)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

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

# ---- Etapa 6: highs (optimización LP/MIP/QP sobre HiGHS) ----
# Misma base que el runtime (3.11): un venv construido con otra versión menor
# de Python no es trasladable entre etapas.
FROM base AS highs-build
WORKDIR /build/highs
COPY highs/requirements.lock .
RUN python3 -m venv /opt/highs-venv \
    && /opt/highs-venv/bin/pip install --no-cache-dir -r requirements.lock
COPY highs/ ./
RUN /opt/highs-venv/bin/pip install --no-cache-dir --no-deps .

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

# Venvs + código de los servicios
COPY --from=clustering-build /opt/clustering-venv /opt/clustering-venv
COPY --from=xgboost-build /opt/xgboost-venv /opt/xgboost-venv
COPY --from=uplift-build /opt/uplift-venv /opt/uplift-venv
COPY --from=transformer-build /opt/transformer-venv /opt/transformer-venv
COPY --from=causal-build /opt/causal-venv /opt/causal-venv
COPY --from=highs-build /opt/highs-venv /opt/highs-venv

COPY --from=clustering-build /build/clustering-api ./clustering-api
COPY --from=xgboost-build /build/xgboost-api ./xgboost-api
COPY --from=uplift-build /build/uplift-api ./uplift-api
COPY --from=transformer-build /build/transformerApi ./transformerApi
COPY --from=causal-build /build/causalTransformer-api ./causalTransformer-api
COPY --from=highs-build /build/highs ./highs

# Proxy y arranque
COPY Caddyfile ./Caddyfile
COPY docker-entrypoint.sh ./docker-entrypoint.sh
RUN chmod +x ./docker-entrypoint.sh

# Puertos de cada servicio (accesibles si se publican con `-p`/compose) + el del
# proxy Caddy (modo Render, un único puerto).
EXPOSE 8010 8011 8012 8013 8014 8015 10000

CMD ["./docker-entrypoint.sh"]
