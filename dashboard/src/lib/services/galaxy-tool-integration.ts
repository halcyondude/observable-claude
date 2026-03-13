/**
 * Galaxy View tool integration helpers.
 *
 * Galaxy View (#15) may not exist yet. These functions provide the data layer
 * so that when GalaxySessionBar.svelte and GalaxyDetailPanel.svelte are built,
 * they can import these directly.
 */

import { getDominantFamily, computeFamilyCounts, TOOL_FAMILIES, type ToolFamily, type FamilyCount } from '$lib/stores/tool-families';

/**
 * Compute a CSS background tint for a session bar based on the dominant tool family.
 * Returns a rgba color at 10% opacity, or null if no tools present.
 */
export function sessionBarTint(toolNames: string[]): string | null {
	const dominant = getDominantFamily(toolNames);
	if (!dominant) return null;
	const hex = TOOL_FAMILIES[dominant].color;
	// Convert hex to rgba at 10% opacity
	const r = parseInt(hex.slice(1, 3), 16);
	const g = parseInt(hex.slice(3, 5), 16);
	const b = parseInt(hex.slice(5, 7), 16);
	return `rgba(${r}, ${g}, ${b}, 0.1)`;
}

/**
 * Check whether a session has any failed tool calls.
 * Use this to decide whether to render the 6px coral failure dot.
 */
export function hasFailedToolCalls(events: Array<{ event_type: string }>): boolean {
	return events.some(e => e.event_type === 'PostToolUseFailure');
}

/**
 * Compute session-level tool stats for the Galaxy detail panel.
 */
export function sessionToolStats(events: Array<{ tool_name?: string; event_type: string; payload?: any }>) {
	const toolNames = events
		.filter(e => e.tool_name && (e.event_type === 'PostToolUse' || e.event_type === 'PostToolUseFailure'))
		.map(e => e.tool_name!);

	const successCount = events.filter(e => e.event_type === 'PostToolUse').length;
	const failCount = events.filter(e => e.event_type === 'PostToolUseFailure').length;

	const durations = events
		.filter(e => (e.event_type === 'PostToolUse' || e.event_type === 'PostToolUseFailure') && (e.payload as any)?.duration_ms)
		.map(e => (e.payload as any).duration_ms as number)
		.sort((a, b) => a - b);

	const medianDurationMs = durations.length > 0
		? durations[Math.floor(durations.length / 2)]
		: undefined;

	return {
		toolNames,
		familyCounts: computeFamilyCounts(toolNames),
		totalCalls: successCount + failCount,
		successCount,
		failCount,
		medianDurationMs
	};
}
