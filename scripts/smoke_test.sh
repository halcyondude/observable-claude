#!/usr/bin/env bash
# V1 Smoke Test for CC Observer
# Validates the full event pipeline: ingest -> DuckDB -> LadybugDB -> API -> SSE

set -euo pipefail

BASE_URL="${COLLECTOR_URL:-http://localhost:4001}"
SESSION_ID="smoke-v1-$(date +%s)"
AGENT_ID="smoke-agent-1"
PASS=0
FAIL=0
TOTAL=0

check() {
  local label="$1"
  local ok="$2"
  ((TOTAL++))
  if [ "$ok" = "true" ]; then
    echo "  PASS  $label"
    ((PASS++))
  else
    echo "  FAIL  $label"
    ((FAIL++))
  fi
}

post_event() {
  local payload="$1"
  curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$BASE_URL/events" \
    -H "Content-Type: application/json" \
    -d "$payload"
}

echo "=== CC Observer V1 Smoke Test ==="
echo "Collector: $BASE_URL"
echo "Session:   $SESSION_ID"
echo ""

# --- Step 1: Health check ---
echo "[1/10] Health check"
health_resp=$(curl -s "$BASE_URL/health" 2>/dev/null || echo '{}')
health_ok=$(echo "$health_resp" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('true' if d.get('status') == 'ok' else 'false')
except: print('false')
" 2>/dev/null)
check "GET /health returns ok" "$health_ok"

if [ "$health_ok" != "true" ]; then
  echo ""
  echo "Collector not reachable at $BASE_URL — is the stack running?"
  exit 1
fi

# --- Step 2: Ingest full session lifecycle ---
echo "[2/10] Ingesting session lifecycle (6 events)"

status=$(post_event '{"event":{"event_type":"SessionStart"},"session":{"session_id":"'"$SESSION_ID"'","cwd":"/tmp/smoke-test"}}')
check "SessionStart accepted ($status)" "$([ "$status" -ge 200 ] && [ "$status" -lt 300 ] && echo true || echo false)"

status=$(post_event '{"event":{"event_type":"SubagentStart","parent_agent_id":null,"prompt":"Run smoke test","depth":0},"session":{"session_id":"'"$SESSION_ID"'","agent_id":"'"$AGENT_ID"'","agent_type":"general-purpose"}}')
check "SubagentStart accepted" "$([ "$status" -ge 200 ] && [ "$status" -lt 300 ] && echo true || echo false)"

status=$(post_event '{"event":{"event_type":"PreToolUse","tool_use_id":"tu-1","tool_name":"Bash","tool_input":{"command":"echo hello"}},"session":{"session_id":"'"$SESSION_ID"'","agent_id":"'"$AGENT_ID"'"}}')
check "PreToolUse accepted" "$([ "$status" -ge 200 ] && [ "$status" -lt 300 ] && echo true || echo false)"

status=$(post_event '{"event":{"event_type":"PostToolUse","tool_use_id":"tu-1","tool_name":"Bash","duration_ms":42,"tool_response":"hello"},"session":{"session_id":"'"$SESSION_ID"'","agent_id":"'"$AGENT_ID"'"}}')
check "PostToolUse accepted" "$([ "$status" -ge 200 ] && [ "$status" -lt 300 ] && echo true || echo false)"

status=$(post_event '{"event":{"event_type":"SubagentStop"},"session":{"session_id":"'"$SESSION_ID"'","agent_id":"'"$AGENT_ID"'"}}')
check "SubagentStop accepted" "$([ "$status" -ge 200 ] && [ "$status" -lt 300 ] && echo true || echo false)"

status=$(post_event '{"event":{"event_type":"SessionEnd"},"session":{"session_id":"'"$SESSION_ID"'"}}')
check "SessionEnd accepted" "$([ "$status" -ge 200 ] && [ "$status" -lt 300 ] && echo true || echo false)"

sleep 0.5

# --- Step 3: Verify DuckDB events ---
echo "[3/10] Verifying DuckDB events"
event_count=$(curl -s "$BASE_URL/api/events?session_id=$SESSION_ID" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    events = data if isinstance(data, list) else data.get('events', [])
    print(len(events))
except: print(0)
" 2>/dev/null)
check "6 events stored in DuckDB (got $event_count)" "$([ "$event_count" = "6" ] && echo true || echo false)"

# --- Step 4: Verify session queries ---
echo "[4/10] Verifying session queries"
has_session=$(curl -s "$BASE_URL/api/sessions" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = data if isinstance(data, list) else data.get('sessions', [])
    print('true' if any(s.get('session_id') == '$SESSION_ID' for s in sessions) else 'false')
except: print('false')
" 2>/dev/null)
check "Session appears in /api/sessions" "$has_session"

summary_ok=$(curl -s "$BASE_URL/api/sessions/summary" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('true' if d.get('total', 0) > 0 else 'false')
except: print('false')
" 2>/dev/null)
check "Session summary shows total > 0" "$summary_ok"

# --- Step 5: Verify LadybugDB graph ---
echo "[5/10] Verifying LadybugDB graph"
graph_ok=$(curl -s "$BASE_URL/api/sessions/$SESSION_ID/graph" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    nodes = d.get('nodes', [])
    edges = d.get('edges', [])
    has_session = any(n['data']['type'] == 'Session' for n in nodes)
    has_agent = any(n['data']['type'] == 'Agent' for n in nodes)
    has_tool = any(n['data']['type'] == 'Tool' for n in nodes)
    print('true' if has_session and has_agent and has_tool else 'false')
except: print('false')
" 2>/dev/null)
check "Graph has Session, Agent, and Tool nodes" "$graph_ok"

# --- Step 6: Verify timeline ---
echo "[6/10] Verifying timeline"
timeline_ok=$(curl -s "$BASE_URL/api/sessions/$SESSION_ID/timeline" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    agents = data if isinstance(data, list) else []
    has_tools = any(len(a.get('tool_events', [])) > 0 for a in agents)
    print('true' if len(agents) > 0 and has_tools else 'false')
except: print('false')
" 2>/dev/null)
check "Timeline has agents with tool events" "$timeline_ok"

# --- Step 7: Verify messages (extracted from SubagentStop/PreToolUse/PostToolUse) ---
echo "[7/10] Verifying message extraction"
msg_count=$(curl -s "$BASE_URL/api/sessions/$SESSION_ID/messages" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    msgs = data if isinstance(data, list) else []
    print(len(msgs))
except: print(0)
" 2>/dev/null)
check "Messages extracted from events (got $msg_count, expect >= 3)" "$([ "$msg_count" -ge 3 ] 2>/dev/null && echo true || echo false)"

# --- Step 8: Save session ---
echo "[8/10] Verifying save/unsave"
save_status=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/api/sessions/$SESSION_ID/save" \
  -H "Content-Type: application/json" \
  -d '{"name":"Smoke Test Session"}')
check "Save session returns 2xx ($save_status)" "$([ "$save_status" -ge 200 ] && [ "$save_status" -lt 300 ] && echo true || echo false)"

saved_list=$(curl -s "$BASE_URL/api/sessions/saved" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    sessions = data if isinstance(data, list) else []
    print('true' if any(s.get('session_id') == '$SESSION_ID' for s in sessions) else 'false')
except: print('false')
" 2>/dev/null)
check "Session appears in saved list" "$saved_list"

# --- Step 9: Export session ---
echo "[9/10] Verifying export/import"
export_status=$(curl -s -o /tmp/smoke_export.ccobs -w "%{http_code}" "$BASE_URL/api/sessions/$SESSION_ID/export")
check "Export returns 2xx ($export_status)" "$([ "$export_status" -ge 200 ] && [ "$export_status" -lt 300 ] && echo true || echo false)"

if [ "$export_status" -ge 200 ] && [ "$export_status" -lt 300 ]; then
  export_ok=$(python3 -c "
import gzip, json
try:
    with open('/tmp/smoke_export.ccobs', 'rb') as f:
        data = json.loads(gzip.decompress(f.read()))
    has_events = len(data.get('events', [])) > 0
    has_messages = 'messages' in data
    has_workspace = 'workspace' in data.get('session', {})
    print('true' if has_events and has_messages and has_workspace else 'false')
except: print('false')
" 2>/dev/null)
  check "Export has events, messages, and workspace metadata" "$export_ok"
fi

# --- Step 10: Workspace grouping + Cypher ---
echo "[10/10] Verifying workspace grouping and Cypher"
grouped_ok=$(curl -s "$BASE_URL/api/sessions/grouped" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    groups = data if isinstance(data, list) else []
    has_workspace = any(g.get('workspace', {}).get('path') for g in groups)
    has_sessions = any(len(g.get('sessions', [])) > 0 for g in groups)
    print('true' if has_workspace and has_sessions else 'false')
except: print('false')
" 2>/dev/null)
check "Grouped sessions have workspace paths and sessions" "$grouped_ok"

cypher_status=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE_URL/api/cypher" \
  -H "Content-Type: application/json" \
  -d '{"cypher":"MATCH (s:Session {session_id: \"'"$SESSION_ID"'\"}) RETURN s.session_id"}')
check "Cypher query returns 2xx ($cypher_status)" "$([ "$cypher_status" -ge 200 ] && [ "$cypher_status" -lt 300 ] && echo true || echo false)"

# --- Cleanup ---
curl -s -o /dev/null -X DELETE "$BASE_URL/api/sessions/$SESSION_ID/save" 2>/dev/null || true
rm -f /tmp/smoke_export.ccobs

# --- Summary ---
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
