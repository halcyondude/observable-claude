---
name: oc:setup
description: Configure CC Observer environment (API key, Docker, dependencies)
allowed-tools: Bash, Read, Write, Edit
---

Help the user set up the CC Observer environment. Walk through each step interactively.

## 1. Check Docker

Run `docker --version` and `docker compose version`. If either is missing, tell the user to install Docker Desktop.

## 2. Anthropic API Key

Check if `ANTHROPIC_API_KEY` is set in the current environment:
```bash
echo ${ANTHROPIC_API_KEY:+SET}
```

If NOT set:
1. Check common locations for an existing key:
   - `~/.anthropic/api_key`
   - `~/.config/anthropic/api_key`
   - `.env` file in the project root
   - Shell profile files (`~/.zshrc`, `~/.bashrc`) for existing exports
2. If found somewhere, offer to source it or add it to the project `.env`
3. If not found anywhere, tell the user:
   - "I need an Anthropic API key for the NL→Cypher query feature. You can get one at https://console.anthropic.com/settings/keys"
   - Ask them to paste it
   - Write it to `${CLAUDE_PLUGIN_ROOT}/.env` as `ANTHROPIC_API_KEY=<key>`
   - Verify the key works: `curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages -H "x-api-key: $KEY" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}'` — should return 200

If the key IS already set, confirm it's valid with the same check.

## 3. Verify Docker Compose Config

Check that `docker-compose.yml` exists and has the expected services:
```bash
docker compose config --services
```
Should list `collector` and `dashboard`.

## 4. Report

Summarize what's configured:
- Docker: ✓/✗
- Anthropic API Key: ✓/✗ (and where it's sourced from)
- Docker Compose: ✓/✗
- Ready to start: yes/no

If everything is ready, suggest running `/oc:start`.
