import { writable, derived } from 'svelte/store';
import type { ObserverEvent } from '$lib/types/events';

const MAX_EVENTS = 10_000;

function createEventStore() {
	const { subscribe, update, set } = writable<ObserverEvent[]>([]);

	return {
		subscribe,
		set,
		push(event: ObserverEvent) {
			update((events) => {
				const next = [event, ...events];
				if (next.length > MAX_EVENTS) {
					next.length = MAX_EVENTS;
				}
				return next;
			});
		},
		clear() {
			set([]);
		}
	};
}

export const events = createEventStore();

export const toolEvents = derived(events, ($events) =>
	$events.filter(
		(e) =>
			e.event_type === 'PreToolUse' ||
			e.event_type === 'PostToolUse' ||
			e.event_type === 'PostToolUseFailure'
	)
);

export const agentCount = derived(events, ($events) => {
	const running = new Set<string>();
	const ended = new Set<string>();
	for (const e of $events) {
		if (e.event_type === 'SubagentStart' && e.agent_id) {
			running.add(e.agent_id);
		}
		if (e.event_type === 'SubagentEnd' && e.agent_id) {
			ended.add(e.agent_id);
		}
	}
	for (const id of ended) {
		running.delete(id);
	}
	return { active: running.size, total: running.size + ended.size };
});

export const toolNames = derived(events, ($events) => {
	const names = new Set<string>();
	for (const e of $events) {
		if (e.tool_name) names.add(e.tool_name);
	}
	return Array.from(names).sort();
});

export const unreadToolCount = writable(0);

/** Filter events by session_id. Returns a derived store scoped to one session. */
export function getSessionEvents(sessionId: string) {
	return derived(events, ($events) => $events.filter((e) => e.session_id === sessionId));
}

/** Filter events by session_id (non-reactive, for one-shot reads). */
export function filterEventsBySession(allEvents: ObserverEvent[], sessionId: string): ObserverEvent[] {
	return allEvents.filter((e) => e.session_id === sessionId);
}
