FROM python:3.13
LABEL name="image-regresion-backend"
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# Render inyecta la variable PORT (por defecto 10000).
# Se usa ${PORT:-5000} para que siga funcionando en local con docker run -p 5002:5000.
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-5000} main:app"]
