<script lang="ts">
	import { TOOL_FAMILIES, getToolFamily, type ToolFamily } from '$lib/stores/tool-families';

	let {
		toolCalls,
		height = 12
	}: {
		toolCalls: Array<{ name: string }>;
		height?: number;
	} = $props();

	let hoveredFamily = $state<ToolFamily | null>(null);

	const familyCounts = $derived.by(() => {
		const counts: Record<ToolFamily, number> = { file: 0, exec: 0, agent: 0, mcp: 0, meta: 0 };
		for (const call of toolCalls) {
			counts[getToolFamily(call.name)]++;
		}
		return counts;
	});

	const total = $derived(toolCalls.length);

	const segments = $derived.by(() => {
		if (total === 0) return [];
		const order: ToolFamily[] = ['file', 'exec', 'agent', 'mcp', 'meta'];
		return order
			.filter((f) => familyCounts[f] > 0)
			.map((family) => ({
				family,
				count: familyCounts[family],
				pct: (familyCounts[family] / total) * 100,
				color: TOOL_FAMILIES[family].color
			}));
	});
</script>

<div
	class="flex rounded-sm overflow-hidden relative"
	style="height: {height}px; background: var(--color-surface-2);"
	role="img"
	aria-label="Tool family distribution"
>
	{#each segments as seg (seg.family)}
		<div
			class="transition-opacity duration-150"
			style="width: {seg.pct}%; background: {seg.color}; opacity: {hoveredFamily && hoveredFamily !== seg.family ? 0.3 : 1};"
			onmouseenter={() => hoveredFamily = seg.family}
			onmouseleave={() => hoveredFamily = null}
			title="{seg.family}: {seg.count} ({Math.round(seg.pct)}%)"
			role="presentation"
		></div>
	{/each}
</div>
