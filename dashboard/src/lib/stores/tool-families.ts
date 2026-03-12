export const TOOL_FAMILIES = {
	file: { tools: ['Read', 'Write', 'Edit', 'Glob', 'Grep'], color: '#7EB8DA', icon: 'document' },
	exec: { tools: ['Bash'], color: '#B8A9E8', icon: 'terminal' },
	agent: { tools: ['Agent'], color: '#0A9396', icon: 'network' },
	mcp: { prefix: 'mcp__', color: '#E8A87C', icon: 'plug' },
	meta: { tools: ['TodoRead', 'TodoWrite', 'TaskCreate', 'ToolSearch'], color: '#94D2BD', icon: 'clipboard' }
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

export function getToolCssVar(toolName: string): string {
	const family = getToolFamily(toolName);
	return `var(--tool-${family})`;
}
