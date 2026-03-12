import { derived } from 'svelte/store';
import { sessionMap } from '$lib/stores/session';
import type { WorkspaceState } from '$lib/types/events';

/**
 * Derived store that groups sessions by cwd path.
 * Sorted: workspaces with active sessions first (by most recent start),
 * then completed-only workspaces (by most recent end).
 */
export const workspaces = derived(sessionMap, ($map) => {
	const byPath = new Map<string, WorkspaceState>();

	for (const session of $map.values()) {
		const path = session.cwd;
		let ws = byPath.get(path);
		if (!ws) {
			const segments = path.split('/').filter(Boolean);
			ws = {
				path,
				name: segments.length > 0 ? segments[segments.length - 1] : path,
				sessions: [],
				activeCount: 0,
				totalCount: 0
			};
			byPath.set(path, ws);
		}
		ws.sessions.push(session.session_id);
		ws.totalCount++;
		if (session.status === 'active') {
			ws.activeCount++;
		}
	}

	const result = Array.from(byPath.values());

	// Sort: active workspaces first (by most recent session start), then completed
	result.sort((a, b) => {
		if (a.activeCount > 0 && b.activeCount === 0) return -1;
		if (a.activeCount === 0 && b.activeCount > 0) return 1;

		// Within same activity tier, sort by most recent session start
		const latestStart = (ws: WorkspaceState) => {
			let latest = 0;
			for (const sid of ws.sessions) {
				const session = $map.get(sid);
				if (session) {
					const ts = new Date(session.start_ts).getTime();
					if (ts > latest) latest = ts;
				}
			}
			return latest;
		};

		return latestStart(b) - latestStart(a);
	});

	return result;
});
