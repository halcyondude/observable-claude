#!/bin/bash
set -euo pipefail

# Captures or updates visual regression baselines.
# Run this after intentional UI changes to regenerate golden screenshots.
#
# Prerequisites:
#   - Dashboard running at localhost:4242 (docker compose up)
#   - Playwright installed (npx playwright install chromium)
#
# Usage:
#   ./scripts/update-baselines.sh              # update all baselines
#   ./scripts/update-baselines.sh galaxy       # update only tests matching "galaxy"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(dirname "$SCRIPT_DIR")"

cd "$DASHBOARD_DIR"

FILTER="${1:-}"

if [ -n "$FILTER" ]; then
  echo "Updating baselines for tests matching: $FILTER"
  npx playwright test visual-regression -g "$FILTER" --update-snapshots
else
  echo "Updating all visual regression baselines..."
  npx playwright test visual-regression --update-snapshots
fi

echo ""
echo "Baselines updated. Review changes in:"
echo "  dashboard/tests/e2e/screenshots/"
echo ""
echo "If the screenshots look correct, commit them."
