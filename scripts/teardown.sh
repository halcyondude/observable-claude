#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Stopping CC Observer stack..."
docker compose down

echo "Stack stopped."
docker compose ps
