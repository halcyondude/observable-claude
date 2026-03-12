<script lang="ts">
	import type { SessionInfo } from '$lib/types/events';

	let {
		session,
		timeStart,
		timeEnd,
		isSelected = false,
		onclick
	}: {
		session: SessionInfo;
		timeStart: number;
		timeEnd: number;
		isSelected?: boolean;
		onclick: () => void;
	} = $props();

	const totalRange = $derived(timeEnd - timeStart);

	const sessionStart = $derived(new Date(session.start_time).getTime());
	const sessionEnd = $derived(
		session.end_time ? new Date(session.end_time).getTime() : Date.now()
	);

	// Clamp to visible range
	const visibleStart = $derived(Math.max(sessionStart, timeStart));
	const visibleEnd = $derived(Math.min(sessionEnd, timeEnd));

	const leftPct = $derived(((visibleStart - timeStart) / totalRange) * 100);
	const widthPct = $derived(((visibleEnd - visibleStart) / totalRange) * 100);

	// Bar height: 24px base + 2px per agent, max 40px
	const barHeight = $derived(Math.min(40, 24 + (session.agent_count ?? 0) * 2));

	const isActive = $derived(session.is_active);
	const isFailed = $derived(session.end_time && !session.is_active && (session as any).status === 'failed');

	// Show inline labels only if bar is wide enough
	const barWidthPx = $derived(widthPct > 0 ? (widthPct / 100) * 1200 : 0); // rough estimate

	const sessionIdShort = $derived(
		session.session_id.length > 12
			? session.session_id.slice(0, 12) + '...'
			: session.session_id
	);

	function formatDuration(ms: number): string {
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
		return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
	}

	const duration = $derived(formatDuration(sessionEnd - sessionStart));
	const tooltipText = $derived(
		`${session.session_id}\n${duration} | ${session.agent_count} agents | ${session.event_count} events`
	);
</script>

<button
	class="absolute rounded-sm cursor-pointer border-none text-left overflow-hidden"
	style="
		left: {leftPct}%;
		width: {widthPct}%;
		height: {barHeight}px;
		min-width: 4px;
		background: {isActive ? 'rgba(10, 147, 150, 0.8)' : 'var(--color-surface-2)'};
		border: {isSelected ? '2px solid var(--color-primary)' : isFailed ? 'none' : '1px solid var(--color-border)'};
		{isFailed ? 'border-left: 4px solid var(--color-error);' : ''}
		transition: filter 0.15s ease;
	"
	title={tooltipText}
	{onclick}
	onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.filter = 'brightness(1.2)'; }}
	onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.filter = ''; }}
>
	{#if widthPct > 6}
		<div class="flex items-center gap-2 px-1.5 h-full text-xs whitespace-nowrap overflow-hidden">
			<span class="font-mono opacity-80" style="font-size: 11px; color: {isActive ? 'white' : 'var(--color-text-muted)'};">
				{sessionIdShort}
			</span>
			{#if widthPct > 12}
				{#if (session as any).branch}
					<span style="font-size: 11px; color: {isActive ? 'rgba(255,255,255,0.6)' : 'var(--color-text-muted)'};">
						{(session as any).branch}
					</span>
				{/if}
			{/if}
			{#if session.agent_count > 0 && widthPct > 10}
				<span
					class="ml-auto px-1 py-0.5 rounded text-xs font-medium"
					style="background: rgba(0,0,0,0.3); color: {isActive ? 'white' : 'var(--color-text-muted)'}; font-size: 10px;"
				>
					{session.agent_count}
				</span>
			{/if}
		</div>
	{/if}

	{#if isActive}
		<!-- Animated growing edge -->
		<div
			class="absolute top-0 bottom-0 right-0"
			style="
				width: 8px;
				background: linear-gradient(to right, transparent, rgba(10, 147, 150, 0.6));
				border-right: 2px solid var(--color-primary);
				animation: pulse-border 2s ease-in-out infinite;
			"
		></div>
	{/if}
</button>
