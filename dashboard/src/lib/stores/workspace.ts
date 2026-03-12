import { writable, derived, get } from 'svelte/store';
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

export type RecencyPreset = '1h' | '4h' | '24h' | '7d' | 'all';

const RECENCY_KEY = 'galaxy-recency-preset';

function loadRecencyPreset(): RecencyPreset {
	if (typeof window === 'undefined') return '24h';
	const stored = localStorage.getItem(RECENCY_KEY);
	if (stored && ['1h', '4h', '24h', '7d', 'all'].includes(stored)) {
		return stored as RecencyPreset;
	}
	return '24h';
}

export const recencyPreset = writable<RecencyPreset>(loadRecencyPreset());

// Persist to localStorage on change
if (typeof window !== 'undefined') {
	recencyPreset.subscribe((val) => {
		localStorage.setItem(RECENCY_KEY, val);
	});
}

/** Convert a recency preset to an ISO 8601 since timestamp, or undefined for 'all' */
export function presetToSince(preset: RecencyPreset): string | undefined {
	if (preset === 'all') return undefined;
	const ms: Record<string, number> = {
		'1h': 60 * 60 * 1000,
		'4h': 4 * 60 * 60 * 1000,
		'24h': 24 * 60 * 60 * 1000,
		'7d': 7 * 24 * 60 * 60 * 1000
	};
	return new Date(Date.now() - ms[preset]).toISOString();
}

export const workspaces = writable<WorkspaceGroup[]>([]);
export const selectedGalaxySessionId = writable<string | null>(null);
export const timeRange = writable<{ start: number; end: number } | null>(null);
export const collapsedWorkspaces = writable<Set<string>>(new Set());

/** Keyboard navigation focus state */
export const focusedLaneIndex = writable<number>(-1);
export const focusedBarIndex = writable<number>(-1);

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

/** Total session count across all workspaces */
export const totalSessionCount = derived(workspaces, ($workspaces) => {
	return $workspaces.reduce((sum, ws) => sum + ws.total_count, 0);
});

/** Total active session count across all workspaces */
export const activeSessionCount = derived(workspaces, ($workspaces) => {
	return $workspaces.reduce((sum, ws) => sum + ws.active_count, 0);
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
