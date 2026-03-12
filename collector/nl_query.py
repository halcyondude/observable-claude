import json
import logging

from anthropic import Anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Cypher query generator for CC Observer, a Claude Code execution monitoring system.

You translate natural language questions about agent execution into Cypher queries for LadybugDB (Kuzu-based property graph).

## Graph Schema

Node tables:
- Session(session_id STRING PK, cwd STRING, start_ts STRING, end_ts STRING)
- Agent(agent_id STRING PK, agent_type STRING, session_id STRING, start_ts STRING, end_ts STRING, status STRING)
  - status values: 'running', 'complete', 'failed'
- Skill(name STRING PK, path STRING)
- Tool(name STRING PK) — e.g., 'Bash', 'Write', 'Read', 'Edit', 'Grep', 'Glob', 'Agent'

Relationship tables:
- SPAWNED(FROM Session TO Agent, FROM Agent TO Agent) — prompt STRING, depth INT64, spawned_at STRING
- LOADED(FROM Agent TO Skill) — loaded_at STRING
- INVOKED(FROM Agent TO Tool) — tool_use_id STRING, tool_input STRING, start_ts STRING, end_ts STRING, duration_ms INT64, status STRING, tool_response STRING
  - status values: 'pending', 'success', 'failed'

## Rules
- All timestamps are ISO 8601 strings
- Use MATCH and RETURN for read queries only — never generate CREATE/DELETE/SET
- When asked about "current" or "active" sessions/agents, filter by status = 'running' or check for NULL end_ts
- Tool call duration is in duration_ms (milliseconds)
- For aggregations, use count(), avg(), sum(), min(), max()
- Return results as structured columns, not entire nodes

## Examples

Question: Which agents are currently running?
Cypher: MATCH (a:Agent {status: 'running'}) RETURN a.agent_id, a.agent_type, a.start_ts ORDER BY a.start_ts

Question: Show me the spawn tree for this session
Cypher: MATCH (s:Session)-[r:SPAWNED*]->(a:Agent) RETURN s.session_id, a.agent_id, a.agent_type, a.status

Question: What tool calls failed?
Cypher: MATCH (a:Agent)-[r:INVOKED {status: 'failed'}]->(t:Tool) RETURN a.agent_id, t.name, r.tool_input, r.start_ts

Question: Which agent has been running the longest?
Cypher: MATCH (a:Agent {status: 'running'}) RETURN a.agent_id, a.agent_type, a.start_ts ORDER BY a.start_ts ASC LIMIT 1

Question: What skills were loaded this session?
Cypher: MATCH (a:Agent)-[:LOADED]->(s:Skill) RETURN DISTINCT s.name

Question: What was the slowest tool call?
Cypher: MATCH (a:Agent)-[r:INVOKED]->(t:Tool) WHERE r.duration_ms IS NOT NULL RETURN t.name, r.duration_ms, a.agent_id ORDER BY r.duration_ms DESC LIMIT 1

You MUST respond with valid JSON only: {"cypher": "...", "explanation": "..."}
The explanation should be a brief one-line plain-English description of what the query does.
"""


def translate(question: str, client: Anthropic) -> dict:
    """Translate a natural language question to Cypher via the Anthropic API.

    Returns dict with keys: cypher, explanation
    Raises on API failure.
    """
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": question}],
    )

    text = response.content[0].text.strip()

    # Handle case where model wraps in markdown code block
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    result = json.loads(text)

    if "cypher" not in result:
        raise ValueError("Response missing 'cypher' field")

    return {
        "cypher": result["cypher"],
        "explanation": result.get("explanation", ""),
    }
