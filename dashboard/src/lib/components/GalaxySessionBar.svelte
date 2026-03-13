<script lang="ts">
	import type { AgentStatus } from '$lib/types/events';

	let {
		sessionId = '',
		status = 'running' as AgentStatus,
		eventCount = 0,
		duration = '',
		saved = false,
		onsave = () => {},
		onclick = () => {},
	}: {
		sessionId?: string;
		status?: AgentStatus;
		eventCount?: number;
		duration?: string;
		saved?: boolean;
		onsave?: () => void;
		onclick?: () => void;
	} = $props();

	const statusColors: Record<AgentStatus, string> = {
		running: 'var(--color-primary)',
		complete: 'var(--color-surface-2)',
		failed: 'var(--color-error)',
	};

	const borderStyle = $derived(
		status === 'running'
			? `border: 2px solid ${statusColors[status]}; animation: pulse-border 2s ease-in-out infinite;`
			: `border: 2px solid ${statusColors[status]};`
	);

	function truncateId(id: string): string {
		return id.length > 8 ? id.slice(0, 8) : id;
	}
</script>

<div
	class="flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer"
	style="
		background: var(--color-surface);
		{borderStyle}
		transition: background 0.15s ease;
	"
	onclick={() => onclick()}
	onkeydown={(e) => { if (e.key === 'Enter') onclick(); }}
	role="button"
	tabindex="0"
>
	<div class="flex-1 min-w-0">
		<div class="flex items-center gap-2">
			<span class="text-xs font-mono font-medium" style="color: var(--color-text);">
				{truncateId(sessionId)}
			</span>
			{#if status === 'running'}
				<span
					class="inline-block w-1.5 h-1.5 rounded-full"
					style="background: var(--color-primary); animation: pulse-dot 1.5s ease-in-out infinite;"
				></span>
			{/if}
		</div>
		<div class="flex gap-2 mt-0.5 text-xs" style="color: var(--color-text-muted);">
			<span>{eventCount} events</span>
			{#if duration}
				<span>{duration}</span>
			{/if}
		</div>
	</div>

	<button
		class="cursor-pointer border-none text-sm shrink-0"
		style="background: transparent; color: {saved ? 'var(--color-warning)' : 'var(--color-text-muted)'};"
		onclick={(e: MouseEvent) => { e.stopPropagation(); onsave(); }}
		title={saved ? 'Unsave' : 'Save'}
	>
		{saved ? '★' : '☆'}
	</button>
</div>
