import type {
	SessionInfo,
	SessionGraph,
	TimelineAgent,
	ObserverEvent,
	QueryResult,
	AgentMessage,
	MessageSearchResult,
	MessageSearchParams
} from '$lib/types/events';
import type { WorkspaceGroup, ActivityData } from '$lib/stores/workspace';

const BASE = '';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
	const res = await fetch(`${BASE}${url}`, init);
	if (!res.ok) {
		throw new Error(`API error: ${res.status} ${res.statusText}`);
	}
	return res.json();
}

export async function fetchSessions(): Promise<SessionInfo[]> {
	return fetchJson('/api/sessions');
}

export async function fetchActiveSessions(): Promise<SessionInfo[]> {
	return fetchJson('/api/sessions/active');
}

export async function fetchSessionGraph(sessionId: string): Promise<SessionGraph> {
	return fetchJson(`/api/sessions/${sessionId}/graph`);
}

export async function fetchSessionTimeline(sessionId: string): Promise<TimelineAgent[]> {
	return fetchJson(`/api/sessions/${sessionId}/timeline`);
}

export async function fetchEvents(params?: {
	session_id?: string;
	event_type?: string;
	agent_id?: string;
	tool_name?: string;
	limit?: number;
	offset?: number;
}): Promise<ObserverEvent[]> {
	const searchParams = new URLSearchParams();
	if (params) {
		for (const [key, value] of Object.entries(params)) {
			if (value !== undefined) searchParams.set(key, String(value));
		}
	}
	const qs = searchParams.toString();
	return fetchJson(`/api/events${qs ? `?${qs}` : ''}`);
}

export async function askQuestion(question: string): Promise<QueryResult> {
	return fetchJson('/api/ask', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ question })
	});
}

export async function executeCypher(cypher: string): Promise<QueryResult> {
	return fetchJson('/api/cypher', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ cypher })
	});
}

export async function getAgentMessages(agentId: string): Promise<AgentMessage[]> {
	return fetchJson(`/api/agents/${agentId}/messages`);
}

export async function searchMessages(params: MessageSearchParams): Promise<MessageSearchResult[]> {
	const searchParams = new URLSearchParams();
	searchParams.set('q', params.q);
	if (params.session_id) searchParams.set('session_id', params.session_id);
	if (params.agent_id) searchParams.set('agent_id', params.agent_id);
	if (params.role) searchParams.set('role', params.role);
	if (params.limit !== undefined) searchParams.set('limit', String(params.limit));
	if (params.offset !== undefined) searchParams.set('offset', String(params.offset));
	return fetchJson(`/api/messages/search?${searchParams.toString()}`);
}

export async function fetchGroupedSessions(since?: string): Promise<WorkspaceGroup[]> {
	const params = new URLSearchParams();
	if (since) params.set('since', since);
	const qs = params.toString();
	return fetchJson(`/api/sessions/grouped${qs ? `?${qs}` : ''}`);
}

export async function fetchActivity(since?: string): Promise<ActivityData> {
	const params = new URLSearchParams();
	if (since) params.set('since', since);
	const qs = params.toString();
	return fetchJson(`/api/sessions/activity${qs ? `?${qs}` : ''}`);
}

export async function replayControl(
	sessionId: string,
	action: 'pause' | 'resume' | 'seek' | 'speed' | 'stop',
	params?: { position?: number; speed?: number }
): Promise<Record<string, unknown>> {
	return fetchJson(`/api/sessions/${sessionId}/replay/control`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ action, ...params })
	});
}

export async function replayStatus(
	sessionId: string
): Promise<{ active: boolean; paused?: boolean; position?: number; total?: number; speed?: number }> {
	return fetchJson(`/api/sessions/${sessionId}/replay/status`);
}
