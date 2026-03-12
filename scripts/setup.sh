#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Starting CC Observer stack..."
docker compose up -d --build

echo "Waiting for collector to be healthy..."
for i in 1 2 3; do
  if curl -sf http://localhost:4001/health > /dev/null 2>&1; then
    echo "Collector is healthy."
    docker compose ps
    exit 0
  fi
  echo "  Attempt $i/3 — retrying in 2s..."
  sleep 2
done

echo "ERROR: Collector did not become healthy in time."
docker compose logs collector
exit 1
