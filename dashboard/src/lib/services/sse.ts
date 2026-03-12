import { connectionStatus, reconnectAttempt } from '$lib/stores/connection';
import { events, unreadToolCount } from '$lib/stores/events';
import { activeSessionId, liveSessionId, sessions } from '$lib/stores/session';
import {
	isReplaying, replayPosition, replayTotal, replayPaused, stopReplay
} from '$lib/stores/replay';
import { fetchActiveSessions, fetchSessionGraph } from '$lib/services/api';
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
			events.push(event);

			if (
				event.event_type === 'PreToolUse' ||
				event.event_type === 'PostToolUse' ||
				event.event_type === 'PostToolUseFailure'
			) {
				unreadToolCount.update((n) => n + 1);
			}

			if (event.event_type === 'SessionStart') {
				liveSessionId.set(event.session_id);
				activeSessionId.set(event.session_id);
				refreshSessionState();
			}
		} catch {
			// ignore malformed messages
		}
	};

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
			const latest = activeSessions[0];
			liveSessionId.set(latest.session_id);
			if (!get(activeSessionId)) {
				activeSessionId.set(latest.session_id);
			}
		}
	} catch {
		// collector may not be ready yet
	}
}

let replaySource: EventSource | null = null;

export function connectReplay(sessionId: string, speed: number = 1): void {
	disconnectReplay();

	// Clear existing events so replay starts fresh
	events.clear();

	const url = `/api/sessions/${sessionId}/replay/stream?speed=${speed}`;
	replaySource = new EventSource(url);

	replaySource.onopen = () => {
		isReplaying.set(true);
	};

	replaySource.onmessage = (msg) => {
		try {
			const data = JSON.parse(msg.data);
			const event: ObserverEvent = data;

			// Update replay position from server-injected metadata
			if (data.replay_position !== undefined) {
				replayPosition.set(data.replay_position);
			}
			if (data.replay_total !== undefined) {
				replayTotal.set(data.replay_total);
			}

			events.push(event);

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

	// Handle named events
	replaySource.addEventListener('replay_start', (e: Event) => {
		try {
			const me = e as MessageEvent;
			const data = JSON.parse(me.data);
			replayTotal.set(data.total_events);
			replayPosition.set(0);
		} catch {
			// ignore
		}
	});

	replaySource.addEventListener('replay_end', () => {
		replayPaused.set(true);
	});

	replaySource.onerror = () => {
		// Replay stream ended or errored
		if (replaySource) {
			replaySource.close();
			replaySource = null;
		}
		stopReplay();
	};
}

export function disconnectReplay(): void {
	if (replaySource) {
		replaySource.close();
		replaySource = null;
	}
}
