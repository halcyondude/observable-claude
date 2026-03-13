import { writable, derived, get } from 'svelte/store';
import type { SessionInfo, SessionState, SessionStatus } from '$lib/types/events';

// --- Multi-session state ---

/** All tracked sessions, keyed by session_id */
export const sessionMap = writable<Map<string, SessionState>>(new Map());

/** The currently drilled-into session (for existing single-session views) */
export const activeSessionId = writable<string | null>(null);

/** Set of session IDs currently receiving events via SSE */
export const liveSessionIds = writable<Set<string>>(new Set());

/** Whether the user is viewing an archived (non-live) session */
export const viewingArchived = writable<boolean>(false);

// --- Backward-compatible stores ---

/** Flat session list derived from sessionMap, for existing consumers */
export const sessions = derived(sessionMap, ($map) => {
	const list: SessionInfo[] = [];
	for (const s of $map.values()) {
		list.push({
			session_id: s.session_id,
			cwd: s.cwd,
			start_time: s.start_ts,
			end_time: s.end_ts,
			agent_count: s.agent_count,
			event_count: s.event_count,
			is_active: s.status === 'active'
		});
	}
	return list.sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());
});

/** The most recent live session ID (backward compat for single-session code) */
export const liveSessionId = derived(liveSessionIds, ($ids) => {
	if ($ids.size === 0) return null;
	// Return the most recently added live session
	// Sets iterate in insertion order, so last is most recent
	let last: string | null = null;
	for (const id of $ids) {
		last = id;
	}
	return last;
});

/** The active session's full info, derived for existing views */
export const activeSession = derived(
	[sessionMap, activeSessionId],
	([$map, $activeId]) => {
		if (!$activeId) return null;
		const state = $map.get($activeId);
		if (!state) return null;
		return {
			session_id: state.session_id,
			cwd: state.cwd,
			start_time: state.start_ts,
			end_time: state.end_ts,
			agent_count: state.agent_count,
			event_count: state.event_count,
			is_active: state.status === 'active'
		} as SessionInfo;
	}
);

// --- Session mutation helpers ---

/** Register a new session from a SessionStart event */
export function addSession(sessionId: string, cwd: string, timestamp: string): void {
	sessionMap.update((map) => {
		const next = new Map(map);
		next.set(sessionId, {
			session_id: sessionId,
			cwd,
			status: 'active',
			agent_count: 0,
			event_count: 0,
			start_ts: timestamp,
			end_ts: undefined,
			branch: undefined
		});
		return next;
	});
	liveSessionIds.update((ids) => {
		const next = new Set(ids);
		next.add(sessionId);
		return next;
	});
}

/** Mark a session as completed */
export function endSession(sessionId: string, timestamp: string, failed = false): void {
	sessionMap.update((map) => {
		const session = map.get(sessionId);
		if (!session) return map;
		const next = new Map(map);
		next.set(sessionId, {
			...session,
			status: failed ? 'failed' : 'complete',
			end_ts: timestamp
		});
		return next;
	});
	liveSessionIds.update((ids) => {
		const next = new Set(ids);
		next.delete(sessionId);
		return next;
	});
}

/** Increment event count for a session */
export function incrementSessionEvents(sessionId: string): void {
	sessionMap.update((map) => {
		const session = map.get(sessionId);
		if (!session) return map;
		const next = new Map(map);
		next.set(sessionId, {
			...session,
			event_count: session.event_count + 1
		});
		return next;
	});
}

/** Update agent count for a session */
export function updateSessionAgents(sessionId: string, delta: number): void {
	sessionMap.update((map) => {
		const session = map.get(sessionId);
		if (!session) return map;
		const next = new Map(map);
		next.set(sessionId, {
			...session,
			agent_count: session.agent_count + delta
		});
		return next;
	});
}

/** Bulk-load sessions from an API response */
export function loadSessions(infos: SessionInfo[]): void {
	sessionMap.update((map) => {
		const next = new Map(map);
		for (const info of infos) {
			const existing = next.get(info.session_id);
			next.set(info.session_id, {
				session_id: info.session_id,
				cwd: info.cwd,
				status: info.is_active ? 'active' : 'complete',
				agent_count: info.agent_count,
				event_count: info.event_count,
				start_ts: info.start_time,
				end_ts: info.end_time,
				branch: existing?.branch
			});
		}
		return next;
	});
	// Update live session IDs based on loaded data
	liveSessionIds.update((ids) => {
		const next = new Set(ids);
		for (const info of infos) {
			if (info.is_active) {
				next.add(info.session_id);
			} else {
				next.delete(info.session_id);
			}
		}
		return next;
	});
}

// --- Navigation helpers (backward compat) ---

export function switchToSession(sessionId: string): void {
	activeSessionId.set(sessionId);
	const live = get(liveSessionIds);
	viewingArchived.set(!live.has(sessionId));
}

export function returnToLive(): void {
	const latestLive = get(liveSessionId);
	if (latestLive) {
		activeSessionId.set(latestLive);
		viewingArchived.set(false);
	}
}
