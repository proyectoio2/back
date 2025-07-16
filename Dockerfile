FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema requeridas para psycopg2 y curl
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-server-dev-all \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/base.txt

RUN pip install --no-cache-dir -r requirements/base.txt

COPY . /app/

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"] 