FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY server.py .
COPY secrets_store.py .
COPY templates ./templates
COPY static ./static

RUN pip install --no-cache-dir flask cryptography gunicorn redis

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "server:app", "--workers", "3"]
