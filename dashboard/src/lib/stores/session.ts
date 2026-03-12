import { writable, derived } from 'svelte/store';
import type { SessionInfo } from '$lib/types/events';

export const sessions = writable<SessionInfo[]>([]);
export const activeSessionId = writable<string | null>(null);
export const viewingArchived = writable<boolean>(false);

export const activeSession = derived(
	[sessions, activeSessionId],
	([$sessions, $activeSessionId]) => {
		if (!$activeSessionId) return null;
		return $sessions.find((s) => s.session_id === $activeSessionId) ?? null;
	}
);

export const liveSessionId = writable<string | null>(null);

export function switchToSession(sessionId: string): void {
	activeSessionId.set(sessionId);
	let isLive = false;
	liveSessionId.subscribe((id) => (isLive = id === sessionId))();
	viewingArchived.set(!isLive);
}

export function returnToLive(): void {
	liveSessionId.subscribe((id) => {
		if (id) {
			activeSessionId.set(id);
			viewingArchived.set(false);
		}
	})();
}
