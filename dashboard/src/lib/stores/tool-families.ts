export const TOOL_FAMILIES = {
	file: { tools: ['Read', 'Write', 'Edit', 'Glob', 'Grep'], color: '#7EB8DA', icon: 'document' },
	exec: { tools: ['Bash'], color: '#B8A9E8', icon: 'terminal' },
	agent: { tools: ['Agent'], color: '#0A9396', icon: 'network' },
	mcp: { prefix: 'mcp__', color: '#E8A87C', icon: 'plug' },
	meta: {
		tools: ['TodoRead', 'TodoWrite', 'TaskCreate', 'ToolSearch', 'Skill', 'NotebookEdit'],
		color: '#94D2BD',
		icon: 'clipboard'
	}
} as const;

export type ToolFamily = keyof typeof TOOL_FAMILIES;

export function getToolFamily(toolName: string): ToolFamily {
	if (toolName.startsWith('mcp__')) return 'mcp';
	for (const [family, def] of Object.entries(TOOL_FAMILIES)) {
		if ('tools' in def && (def as { tools: readonly string[] }).tools.includes(toolName)) {
			return family as ToolFamily;
		}
	}
	return 'meta';
}

export function getToolColor(toolName: string): string {
	const family = getToolFamily(toolName);
	return TOOL_FAMILIES[family].color;
}

/**
 * Compute p95 duration for each tool name from a set of tool calls.
 * Returns a map of toolName -> p95 duration in ms.
 */
export function computeP95Durations(
	toolCalls: Array<{ tool_name: string; duration_ms?: number }>
): Map<string, number> {
	const byTool = new Map<string, number[]>();
	for (const tc of toolCalls) {
		if (tc.duration_ms == null) continue;
		const arr = byTool.get(tc.tool_name) ?? [];
		arr.push(tc.duration_ms);
		byTool.set(tc.tool_name, arr);
	}

	const result = new Map<string, number>();
	for (const [name, durations] of byTool) {
		if (durations.length < 2) {
			// Not enough data for meaningful p95, use max
			result.set(name, Math.max(...durations));
			continue;
		}
		durations.sort((a, b) => a - b);
		const idx = Math.ceil(durations.length * 0.95) - 1;
		result.set(name, durations[idx]);
	}
	return result;
}
