import { connectionStatus, reconnectAttempt } from '$lib/stores/connection';
import { events, unreadToolCount, incrementSessionMessageCount } from '$lib/stores/events';
import {
	activeSessionId,
	addSession,
	endSession,
	incrementSessionEvents,
	updateSessionAgents,
	loadSessions
} from '$lib/stores/session';
import { fetchActiveSessions } from '$lib/services/api';
import { get } from 'svelte/store';
import type { ObserverEvent } from '$lib/types/events';

const MAX_RECONNECT_DELAY = 30_000;
const MAX_ATTEMPTS = 5;

let eventSource: EventSource | null = null;
let attempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

export function connectSSE(): void {
	if (eventSource) {
		eventSource.close();
	}

	connectionStatus.set('reconnecting');
	reconnectAttempt.set(attempt);

	eventSource = new EventSource('/stream');

	eventSource.onopen = () => {
		connectionStatus.set('connected');
		attempt = 0;
		reconnectAttempt.set(0);
		refreshSessionState();
	};

	eventSource.onmessage = (msg) => {
		try {
			const event: ObserverEvent = JSON.parse(msg.data);

			// Push to global ring buffer (unchanged)
			events.push(event);

			// Route event to the correct session
			const sessionId = event.session_id;

			if (event.event_type === 'SessionStart') {
				const cwd = event.cwd ?? event.payload?.cwd as string ?? '';
				addSession(sessionId, cwd, event.received_at);

				// Auto-focus the new session if nothing is active
				if (!get(activeSessionId)) {
					activeSessionId.set(sessionId);
				}
			} else if (event.event_type === 'SessionEnd') {
				const failed = event.payload?.status === 'failed';
				endSession(sessionId, event.received_at, failed);
			} else {
				// Increment event count for this session
				incrementSessionEvents(sessionId);
			}

			// Track agent lifecycle
			if (event.event_type === 'SubagentStart') {
				updateSessionAgents(sessionId, 1);
			}

			// Tool use tracking (unchanged)
			if (
				event.event_type === 'PreToolUse' ||
				event.event_type === 'PostToolUse' ||
				event.event_type === 'PostToolUseFailure'
			) {
				unreadToolCount.update((n) => n + 1);
			}
		} catch {
			// ignore malformed messages
		}
	};

	// Handle named 'message' events from collector (touchpoint 5: conversation SSE routing)
	eventSource.addEventListener('message', (msg) => {
		try {
			const data = JSON.parse(msg.data);
			const sessionId = data.session_id;
			if (sessionId) {
				incrementSessionMessageCount(sessionId);
			}
		} catch {
			// ignore malformed message events
		}
	});

	eventSource.onerror = () => {
		eventSource?.close();
		eventSource = null;

		if (attempt < MAX_ATTEMPTS) {
			attempt++;
			const delay = Math.min(1000 * Math.pow(2, attempt - 1), MAX_RECONNECT_DELAY);
			connectionStatus.set('reconnecting');
			reconnectAttempt.set(attempt);
			reconnectTimer = setTimeout(() => connectSSE(), delay);
		} else {
			connectionStatus.set('disconnected');
			reconnectAttempt.set(attempt);
		}
	};
}

export function disconnectSSE(): void {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	if (eventSource) {
		eventSource.close();
		eventSource = null;
	}
	connectionStatus.set('disconnected');
}

export function retrySSE(): void {
	attempt = 0;
	connectSSE();
}

async function refreshSessionState(): Promise<void> {
	try {
		const activeSessions = await fetchActiveSessions();
		if (activeSessions.length > 0) {
			// Bulk-load all sessions into the multi-session store
			loadSessions(activeSessions);

			// Set active session if none selected
			if (!get(activeSessionId)) {
				const latest = activeSessions[0];
				activeSessionId.set(latest.session_id);
			}
		}
	} catch {
		// collector may not be ready yet
	}
}
