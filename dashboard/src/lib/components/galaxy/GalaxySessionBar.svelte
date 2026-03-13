<script lang="ts">
	import type { SessionInfo } from '$lib/types/events';
	import { goto } from '$app/navigation';
	import { activeSessionId } from '$lib/stores/session';

	let {
		session,
		timeStart,
		timeEnd,
		isSelected = false,
		isFocused = false,
		onclick,
		compact = false
	}: {
		session: SessionInfo;
		timeStart: number;
		timeEnd: number;
		isSelected?: boolean;
		isFocused?: boolean;
		onclick: () => void;
		compact?: boolean;
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

	// Check if session is saved/bookmarked
	const isSaved = $derived((session as any).is_saved === true || (session as any).bookmarked === true);

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
		`ID: ${session.session_id}\n` +
		((session as any).branch ? `Branch: ${(session as any).branch}\n` : '') +
		`Duration: ${duration}\n` +
		`Agents: ${session.agent_count}\n` +
		`Events: ${session.event_count}`
	);

	// Border style: focus > selected > failed > default
	const borderStyle = $derived(() => {
		if (isFocused) return '2px solid rgba(10, 147, 150, 0.8)';
		if (isSelected) return '2px solid var(--color-primary)';
		if (isFailed) return 'none';
		return '1px solid var(--color-border)';
	});

	function handleDblClick(e: MouseEvent) {
		e.stopPropagation();
		activeSessionId.set(session.session_id);
		goto(`/tree?session=${session.session_id}`);
	}
</script>

<button
	class="absolute rounded-sm cursor-pointer border-none text-left overflow-hidden"
	style="
		left: {leftPct}%;
		width: {widthPct}%;
		height: {barHeight}px;
		min-width: 4px;
		background: {isActive ? 'rgba(10, 147, 150, 0.8)' : 'var(--color-surface-2)'};
		border: {borderStyle()};
		{isFailed ? 'border-left: 4px solid var(--color-error);' : ''}
		transition: filter 0.15s ease, border-color 0.15s ease;
	"
	title={tooltipText}
	{onclick}
	ondblclick={handleDblClick}
	onmouseenter={(e) => { (e.currentTarget as HTMLElement).style.filter = 'brightness(1.2)'; }}
	onmouseleave={(e) => { (e.currentTarget as HTMLElement).style.filter = ''; }}
>
	{#if !compact && widthPct > 6}
		<div class="flex items-center gap-2 px-1.5 h-full text-xs whitespace-nowrap overflow-hidden">
			{#if isSaved}
				<span style="color: var(--color-warning); font-size: 10px; flex-shrink: 0;" title="Saved session">&#9733;</span>
			{/if}
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
