FROM python:3.11-slim

WORKDIR /app

# Build-Arg mit Default
ARG APP_VERSION="0.0.0"
ENV APP_VERSION=${APP_VERSION}

# Version in Datei schreiben – WICHTIG: APP_VERSION benutzen
RUN echo "${APP_VERSION}" > /app/version.txt

COPY server.py /app/
COPY secrets_store.py /app/
COPY templates /app/templates
COPY static /app/static

RUN mkdir -p /app/data

RUN pip install --no-cache-dir flask cryptography gunicorn redis

EXPOSE 5000

CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:5000", "server:app"]
