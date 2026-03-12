<script lang="ts">
	let {
		toolCalls
	}: {
		toolCalls: Array<{ name: string; status: string; duration_ms?: number }>;
	} = $props();

	const total = $derived(toolCalls.length);

	const successRate = $derived.by(() => {
		if (total === 0) return 0;
		const successes = toolCalls.filter((c) => c.status !== 'failed' && c.status !== 'error').length;
		return Math.round((successes / total) * 100);
	});

	const medianDuration = $derived.by(() => {
		const durations = toolCalls
			.map((c) => c.duration_ms)
			.filter((d): d is number => d != null && d > 0)
			.sort((a, b) => a - b);
		if (durations.length === 0) return null;
		const mid = Math.floor(durations.length / 2);
		return durations.length % 2 === 0
			? Math.round((durations[mid - 1] + durations[mid]) / 2)
			: Math.round(durations[mid]);
	});
</script>

<div class="flex items-center gap-1.5 text-xs" style="color: var(--color-text-muted);">
	<span>
		<span class="font-medium" style="color: var(--color-text);">{total}</span> calls
	</span>
	<span>&middot;</span>
	<span>
		<span
			class="font-medium"
			style="color: {successRate >= 95 ? 'var(--color-success)' : successRate >= 80 ? 'var(--color-warning)' : 'var(--color-error)'};"
		>
			{successRate}%
		</span>
		success
	</span>
	{#if medianDuration != null}
		<span>&middot;</span>
		<span>
			<span class="font-mono font-medium" style="color: var(--color-text);">{medianDuration}ms</span> median
		</span>
	{/if}
</div>
