---
name: observer:status
description: Show CC Observer status
---

Check the health and activity of the CC Observer stack:

1. Query `GET http://localhost:4001/health` for uptime and event count
2. Query `GET http://localhost:4002/api/sessions/active` for live sessions
3. Display:
   - Collector status: up/down
   - Uptime
   - Total events ingested
   - Active sessions (count + session IDs)
   - Running agents (if any active sessions)
   - Dashboard URL: http://localhost:3000
4. If collector is not reachable, report it as down and suggest running `/observer:start`
