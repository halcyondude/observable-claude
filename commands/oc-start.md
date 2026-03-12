---
name: observer:start
description: Start the CC Observer Docker stack
---

Run the setup script to start the CC Observer collector and dashboard:

1. Execute `bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh`
2. The script runs `docker compose up -d` and polls the health endpoint
3. Report the result to the user: collector URL (localhost:4001), dashboard URL (localhost:3000), event count
4. If startup fails, show the Docker logs for debugging
