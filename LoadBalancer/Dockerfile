# Balanceador de carga — imagen multi-etapa (Rust).
#
# Construcción (contexto = LoadBalancer/):
#   docker build -t load-balancer:local -f LoadBalancer/Dockerfile LoadBalancer/
#
# El puerto por defecto es 8016; configurable con LOAD_BALANCER_PORT.

# ── Etapa de compilación ────────────────────────────────────────────
FROM rust:1-slim AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

# ── Etapa de ejecución ──────────────────────────────────────────────
FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/load-balancer /usr/local/bin/load-balancer

EXPOSE 8016
ENV LOAD_BALANCER_PORT=8016
CMD ["load-balancer"]
