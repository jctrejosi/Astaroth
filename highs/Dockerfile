# La imagen usa la misma versión menor de Python que el entorno de desarrollo/CI
# (3.12), como exige la especificación; python:3.11-slim no satisface el pin
# de numpy del lockfile.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

# El código se copia antes de instalar el proyecto: `pip install .` necesita
# el paquete fuente, no solo `pyproject.toml`.
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "highs_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
