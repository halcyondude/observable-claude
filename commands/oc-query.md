---
name: oc:query
description: Query the execution graph with natural language or Cypher
allowed-tools: Bash
---

Query the CC Observer execution graph. The user's question is in $ARGUMENTS.

1. POST the question to `http://localhost:4002/api/ask` with body `{"question": "$ARGUMENTS"}`
2. The API returns `{cypher, explanation, result}`
3. Display:
   - The natural language explanation
   - The generated Cypher query (in a code block)
   - The query results (formatted as a table if tabular)
4. If the API is not reachable, tell the user to start the observer first with `/oc:start`
5. If the query fails, show the error and suggest trying a different phrasing or using raw Cypher via `POST http://localhost:4002/api/cypher`
