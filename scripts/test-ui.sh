#!/usr/bin/env bash
# Prepare the CC Observer stack for UI testing.
# Ensures Docker is running, seeds test data, validates the dashboard.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COLLECTOR_URL="http://localhost:4001"
DASHBOARD_URL="http://localhost:4242"

echo "=== CC Observer UI Test Setup ==="
echo ""

# 1. Check if collector is reachable
echo "[1/4] Checking Docker stack..."
health_status=$(curl -s -o /dev/null -w "%{http_code}" "$COLLECTOR_URL/health" 2>/dev/null || echo "000")

if [ "$health_status" = "000" ] || [ "$health_status" -ge 400 ]; then
    echo "  Stack not running — starting with docker compose..."
    cd "$PROJECT_ROOT"
    docker compose up -d

    echo "  Waiting for collector to become healthy..."
    retries=0
    max_retries=30
    while [ $retries -lt $max_retries ]; do
        health_status=$(curl -s -o /dev/null -w "%{http_code}" "$COLLECTOR_URL/health" 2>/dev/null || echo "000")
        if [ "$health_status" -ge 200 ] && [ "$health_status" -lt 300 ]; then
            break
        fi
        retries=$((retries + 1))
        sleep 2
    done

    if [ $retries -eq $max_retries ]; then
        echo "  FAIL: Collector did not become healthy after ${max_retries} attempts"
        exit 1
    fi
    echo "  Stack is up"
else
    echo "  Stack already running"
fi

# 2. Seed test data
echo "[2/4] Seeding test data..."
cd "$PROJECT_ROOT"
python3 scripts/seed_test_data.py --db-path ./data/duckdb/events.db --graph-path ./data/ladybug

# 3. Validate dashboard is reachable
echo "[3/4] Checking dashboard..."
dash_status=$(curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL" 2>/dev/null || echo "000")

if [ "$dash_status" -ge 200 ] && [ "$dash_status" -lt 400 ]; then
    echo "  Dashboard reachable (HTTP $dash_status)"
else
    echo "  WARN: Dashboard returned HTTP $dash_status — it may still be starting"
fi

# 4. Report
echo "[4/4] Status"
echo ""
echo "  Collector:  $COLLECTOR_URL"
echo "  Dashboard:  $DASHBOARD_URL"
echo ""
echo "  Dashboard ready for testing at $DASHBOARD_URL"
