import { writable, derived } from 'svelte/store';
import type { SessionInfo } from '$lib/types/events';

export interface WorkspaceGroup {
	workspace: string;
	name: string;
	sessions: SessionInfo[];
	active_count: number;
	total_count: number;
}

export interface ActivityBucket {
	timestamp: string;
	counts: Record<string, number>;
}

export interface ActivityData {
	bucket_seconds: number;
	buckets: ActivityBucket[];
}

export const workspaces = writable<WorkspaceGroup[]>([]);
export const selectedGalaxySessionId = writable<string | null>(null);
export const timeRange = writable<{ start: number; end: number } | null>(null);
export const collapsedWorkspaces = writable<Set<string>>(new Set());

/** Workspace color palette for time brush stacking */
const WORKSPACE_COLORS = [
	'#0A9396', '#EE9B00', '#94D2BD', '#CA6702',
	'#BB3E03', '#005F73', '#AE2012', '#9B2226'
];

export function getWorkspaceColor(index: number): string {
	return WORKSPACE_COLORS[index % WORKSPACE_COLORS.length];
}

/** Workspaces sorted: active-first, then by most recent activity */
export const sortedWorkspaces = derived(workspaces, ($workspaces) => {
	return [...$workspaces].sort((a, b) => {
		// Active workspaces first
		if (a.active_count > 0 && b.active_count === 0) return -1;
		if (a.active_count === 0 && b.active_count > 0) return 1;

		// Then by most recent session start
		const aLatest = Math.max(...a.sessions.map((s) => new Date(s.start_time).getTime()));
		const bLatest = Math.max(...b.sessions.map((s) => new Date(s.start_time).getTime()));
		return bLatest - aLatest;
	});
});

export function toggleWorkspaceCollapse(workspace: string): void {
	collapsedWorkspaces.update((set) => {
		const next = new Set(set);
		if (next.has(workspace)) {
			next.delete(workspace);
		} else {
			next.add(workspace);
		}
		return next;
	});
}
