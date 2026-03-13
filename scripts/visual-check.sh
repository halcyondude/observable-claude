#!/usr/bin/env bash
# Captures screenshots of all dashboard views for manual review.
# Fallback for when Playwright MCP tools aren't available.
#
# Usage: bash scripts/visual-check.sh [output-dir]

set -euo pipefail

cd "$(dirname "$0")/.."

OUTPUT_DIR="${1:-./visual-check-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUTPUT_DIR"

# Check if stack is running
if ! curl -sf http://localhost:4001/health > /dev/null 2>&1; then
  echo "ERROR: Collector not reachable at localhost:4001"
  echo "Start the stack first: /oc:start or bash scripts/setup.sh"
  exit 1
fi

# Check if dashboard is reachable
if ! curl -sf http://localhost:4242 > /dev/null 2>&1; then
  echo "ERROR: Dashboard not reachable at localhost:4242"
  echo "Check docker compose logs dashboard"
  exit 1
fi

VIEWS=(
  "galaxy:/"
  "spawn-tree:/spawn-tree"
  "timeline:/timeline"
  "tool-feed:/tool-feed"
  "analytics:/analytics"
  "query:/query"
  "sessions:/sessions"
)

echo "Capturing dashboard screenshots to $OUTPUT_DIR..."
echo ""

for entry in "${VIEWS[@]}"; do
  name="${entry%%:*}"
  route="${entry#*:}"
  url="http://localhost:4242${route}"
  outfile="$OUTPUT_DIR/${name}.png"

  echo "  $name ($url)..."

  # Use Playwright CLI to screenshot each view
  if command -v npx &> /dev/null; then
    npx playwright screenshot \
      --browser chromium \
      --wait-for-timeout 2000 \
      --full-page \
      "$url" "$outfile" 2>/dev/null || {
        echo "    WARN: Failed to capture $name"
        continue
      }
    echo "    Saved: $outfile"
  else
    echo "    SKIP: npx not found — install Node.js and Playwright"
  fi
done

echo ""
echo "Screenshots saved to $OUTPUT_DIR"
echo "Review them manually or use /oc:visual-check for autonomous evaluation."
