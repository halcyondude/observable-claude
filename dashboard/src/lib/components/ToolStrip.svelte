<script lang="ts">
	import ToolPip from './ToolPip.svelte';

	let {
		toolCalls,
		maxPips = 48
	}: {
		toolCalls: Array<{ name: string; status: string }>;
		maxPips?: number;
	} = $props();

	const visible = $derived(toolCalls.slice(0, maxPips));
	const overflow = $derived(Math.max(0, toolCalls.length - maxPips));

	function normalizeStatus(s: string): 'success' | 'failed' | 'pending' {
		if (s === 'failed' || s === 'error') return 'failed';
		if (s === 'pending' || s === 'running') return 'pending';
		return 'success';
	}
</script>

<div class="flex items-center gap-0.5 relative overflow-hidden" style="min-height: 12px;">
	{#each visible as call, i (i)}
		<ToolPip toolName={call.name} status={normalizeStatus(call.status)} />
	{/each}

	{#if overflow > 0}
		<div
			class="absolute top-0 right-0 h-full flex items-center pl-4 pr-1"
			style="background: linear-gradient(to right, transparent, var(--color-surface) 40%);"
		>
			<span class="text-xs font-mono" style="color: var(--color-text-muted); font-size: 10px;">
				+{overflow}
			</span>
		</div>
	{/if}
</div>
