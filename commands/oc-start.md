---
name: oc:start
description: Start the CC Observer Docker stack
---

Start the CC Observer collector and dashboard:

1. Check if `ANTHROPIC_API_KEY` is set in the environment or in `${CLAUDE_PLUGIN_ROOT}/.env`. If neither exists, warn the user that NL→Cypher queries won't work and suggest running `/oc:setup` first. Continue with startup either way — the collector works without the key.
2. Execute `bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh`
3. The script runs `docker compose up -d` and polls the health endpoint
4. Report the result to the user: collector URL (localhost:4001), dashboard URL (localhost:4242), event count
5. If startup fails, show the Docker logs for debugging
