#!/usr/bin/env bash
set -e

# 1) Version bestimmen
if [ -n "$1" ]; then
  VERSION="$1"
else
  # Versuche Git-Tag, sonst Fehler
  if git describe --tags --abbrev=0 >/dev/null 2>&1; then
    VERSION=$(git describe --tags --abbrev=0)
  else
    echo "Fehler: Keine Version angegeben und kein Git-Tag gefunden."
    echo "Nutzung: ./build_release.sh <version>"
    echo "Beispiel: ./build_release.sh 1.0.5"
    exit 1
  fi
fi

# 'v' am Anfang entfernen, falls vorhanden (z.B. v1.0.0 -> 1.0.0)
CLEAN_VERSION="${VERSION#v}"

echo "Building SimpleOTS version: ${CLEAN_VERSION}"

# 2) Docker-Image bauen
docker build \
  --build-arg APP_VERSION="${CLEAN_VERSION}" \
  -t nick1122/simpleots:${CLEAN_VERSION} \
  -t nick1122/simpleots:latest \
  .

# 3) Push zu Docker Hub
docker push nick1122/simpleots:${CLEAN_VERSION}
docker push nick1122/simpleots:latest

echo "--------------------------------------------------------"
echo "FERTIG!"
echo "Version ${CLEAN_VERSION} wurde gebaut und hochgeladen."
echo "Docker Hub: https://hub.docker.com/r/nick1122/simpleots"
echo "--------------------------------------------------------"
