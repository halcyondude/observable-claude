#!/usr/bin/env bash
# Smoke test for CC Observer collector.
# Posts a simulated session lifecycle and verifies responses.

set -euo pipefail

BASE_URL="http://localhost:4001"
SESSION_ID="smoke-test-1"
PASS=0
FAIL=0

check() {
  local label="$1"
  local ok="$2"
  if [ "$ok" = "true" ]; then
    echo "  PASS  $label"
    ((PASS++))
  else
    echo "  FAIL  $label"
    ((FAIL++))
  fi
}

post_event() {
  local event_type="$1"
  local payload="$2"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$BASE_URL/events" \
    -H "Content-Type: application/json" \
    -d "$payload")
  [ "$status" -ge 200 ] && [ "$status" -lt 300 ]
}

echo "=== CC Observer Smoke Test ==="
echo ""

# 1. Health check
echo "[1/3] Health check"
health_status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" 2>/dev/null || echo "000")
check "GET /health returns 2xx" "$([ "$health_status" -ge 200 ] 2>/dev/null && [ "$health_status" -lt 300 ] 2>/dev/null && echo true || echo false)"

if [ "$health_status" = "000" ]; then
  echo ""
  echo "Collector not reachable at $BASE_URL — is the stack running?"
  echo "Results: $PASS passed, $FAIL failed"
  exit 1
fi

# 2. Post event sequence
echo "[2/3] Posting event sequence"

events=(
  'SessionStart|{"event_type":"SessionStart","session_id":"'"$SESSION_ID"'","cwd":"/tmp/test"}'
  'SubagentStart|{"event_type":"SubagentStart","session_id":"'"$SESSION_ID"'","agent_id":"agent-1","agent_type":"general-purpose"}'
  'PreToolUse|{"event_type":"PreToolUse","session_id":"'"$SESSION_ID"'","agent_id":"agent-1","tool_use_id":"tool-1","tool_name":"Bash"}'
  'PostToolUse|{"event_type":"PostToolUse","session_id":"'"$SESSION_ID"'","agent_id":"agent-1","tool_use_id":"tool-1","tool_name":"Bash"}'
  'SubagentStop|{"event_type":"SubagentStop","session_id":"'"$SESSION_ID"'","agent_id":"agent-1"}'
  'SessionEnd|{"event_type":"SessionEnd","session_id":"'"$SESSION_ID"'"}'
)

all_posted=true
for entry in "${events[@]}"; do
  etype="${entry%%|*}"
  payload="${entry#*|}"
  if ! post_event "$etype" "$payload"; then
    all_posted=false
    echo "  FAIL  POST $etype"
  fi
done
check "All 6 events accepted" "$all_posted"

# Brief pause for async processing
sleep 0.5

# 3. Verify API responses
echo "[3/3] Verifying API"

sessions_resp=$(curl -s "$BASE_URL/api/sessions")
has_session=$(echo "$sessions_resp" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = data if isinstance(data, list) else data.get('sessions', [])
    print('true' if any(s.get('session_id') == '$SESSION_ID' for s in sessions) else 'false')
except Exception:
    print('false')
" 2>/dev/null)
check "GET /api/sessions contains $SESSION_ID" "$has_session"

events_resp=$(curl -s "$BASE_URL/api/events?session_id=$SESSION_ID")
event_count=$(echo "$events_resp" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    events = data if isinstance(data, list) else data.get('events', [])
    print(len(events))
except Exception:
    print(0)
" 2>/dev/null)
check "GET /api/events returns 6 events (got $event_count)" "$([ "$event_count" = "6" ] && echo true || echo false)"

# Summary
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
