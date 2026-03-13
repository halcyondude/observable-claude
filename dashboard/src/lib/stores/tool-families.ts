export type ToolFamily = 'file' | 'exec' | 'agent' | 'mcp' | 'meta';

export interface ToolFamilyDef {
	color: string;
	icon: string;
	label: string;
	tools?: string[];
	prefix?: string;
}

export const TOOL_FAMILIES: Record<ToolFamily, ToolFamilyDef> = {
	file: { tools: ['Read', 'Write', 'Edit', 'Glob', 'Grep'], color: '#7EB8DA', icon: '\u25A1', label: 'File' },
	exec: { tools: ['Bash'], color: '#B8A9E8', icon: '\u25B7', label: 'Exec' },
	agent: { tools: ['Agent'], color: '#0A9396', icon: '\u25C9', label: 'Agent' },
	mcp: { prefix: 'mcp__', color: '#E8A87C', icon: '\u25C7', label: 'MCP' },
	meta: { tools: ['TodoRead', 'TodoWrite', 'TaskCreate', 'ToolSearch', 'Skill', 'WebSearch', 'WebFetch', 'NotebookEdit'], color: '#94D2BD', icon: '\u25CB', label: 'Meta' }
} as const;

export function getToolFamily(toolName: string): ToolFamily {
	if (!toolName) return 'meta';
	if (toolName.startsWith('mcp__')) return 'mcp';
	for (const [family, def] of Object.entries(TOOL_FAMILIES)) {
		if (def.tools?.includes(toolName)) return family as ToolFamily;
	}
	return 'meta';
}

export function getToolFamilyColor(toolName: string): string {
	return TOOL_FAMILIES[getToolFamily(toolName)].color;
}

export const getToolColor = getToolFamilyColor;

export interface FamilyCount {
	family: ToolFamily;
	count: number;
	color: string;
	label: string;
}

export function computeFamilyCounts(toolNames: string[]): FamilyCount[] {
	const counts: Record<ToolFamily, number> = { file: 0, exec: 0, agent: 0, mcp: 0, meta: 0 };
	for (const name of toolNames) {
		counts[getToolFamily(name)]++;
	}
	return (Object.entries(counts) as [ToolFamily, number][])
		.filter(([, count]) => count > 0)
		.map(([family, count]) => ({
			family,
			count,
			color: TOOL_FAMILIES[family].color,
			label: TOOL_FAMILIES[family].label
		}))
		.sort((a, b) => b.count - a.count);
}

export function getDominantFamily(toolNames: string[]): ToolFamily | null {
	const counts = computeFamilyCounts(toolNames);
	return counts.length > 0 ? counts[0].family : null;
}
