<script lang="ts">
	export type BadgeStatus = 'running' | 'complete' | 'failed' | 'connected' | 'disconnected';

	let {
		status = 'running',
	}: {
		status?: BadgeStatus;
	} = $props();

	const styles: Record<BadgeStatus, { bg: string; text: string; label: string }> = {
		running: { bg: 'var(--color-primary)', text: 'white', label: 'Running' },
		complete: { bg: 'var(--color-surface-2)', text: 'var(--color-text-muted)', label: 'Complete' },
		failed: { bg: 'var(--color-error)', text: 'white', label: 'Failed' },
		connected: { bg: '#22c55e', text: 'white', label: 'Connected' },
		disconnected: { bg: '#ef4444', text: 'white', label: 'Disconnected' },
	};

	const style = $derived(styles[status]);
</script>

<span
	class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium"
	style="background: {style.bg}; color: {style.text};"
>
	{#if status === 'running'}
		<span
			class="inline-block w-1.5 h-1.5 rounded-full"
			style="background: white; animation: pulse-dot 1.5s ease-in-out infinite;"
		></span>
	{/if}
	{style.label}
</span>
