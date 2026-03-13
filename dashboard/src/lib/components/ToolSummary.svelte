<script lang="ts">
	let {
		totalCalls,
		successCount,
		failCount,
		medianDurationMs
	}: {
		totalCalls: number;
		successCount: number;
		failCount: number;
		medianDurationMs?: number;
	} = $props();

	let successRate = $derived(totalCalls > 0 ? Math.round((successCount / totalCalls) * 100) : 0);

	function formatDuration(ms: number): string {
		if (ms < 1000) return `${Math.round(ms)}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}
</script>

<div class="flex items-center gap-3 text-xs" style="color: var(--color-text-muted);">
	<span>{totalCalls} calls</span>
	<span style="color: var(--color-success);">{successRate}% ok</span>
	{#if failCount > 0}
		<span style="color: var(--color-error);">{failCount} failed</span>
	{/if}
	{#if medianDurationMs !== undefined}
		<span>p50 {formatDuration(medianDurationMs)}</span>
	{/if}
</div>
