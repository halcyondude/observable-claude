<script lang="ts">
	import { computeFamilyCounts, type FamilyCount } from '$lib/stores/tool-families';

	let {
		toolNames,
		height = 12
	}: {
		toolNames: string[];
		height?: number;
	} = $props();

	let counts: FamilyCount[] = $derived(computeFamilyCounts(toolNames));
	let total = $derived(toolNames.length);
</script>

{#if total > 0}
	<div
		class="flex w-full rounded overflow-hidden"
		style="height: {height}px;"
		title="Tool family distribution"
	>
		{#each counts as segment}
			{@const pct = (segment.count / total) * 100}
			<div
				style="width: {pct}%; background: {segment.color}; min-width: 2px;"
				title="{segment.label}: {segment.count} ({Math.round(pct)}%)"
			></div>
		{/each}
	</div>
{/if}
