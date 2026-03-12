<script lang="ts">
	import { connectionStatus, reconnectAttempt } from '$lib/stores/connection';
	import { activeSession } from '$lib/stores/session';
	import { agentCount } from '$lib/stores/events';
	import { retrySSE } from '$lib/services/sse';

	let elapsed = $state('');
	let interval: ReturnType<typeof setInterval> | undefined;

	$effect(() => {
		if (interval) clearInterval(interval);
		const session = $activeSession;
		if (session?.start_time) {
			const updateElapsed = () => {
				const start = new Date(session.start_time).getTime();
				const now = Date.now();
				const diff = Math.floor((now - start) / 1000);
				const h = Math.floor(diff / 3600);
				const m = Math.floor((diff % 3600) / 60);
				const s = diff % 60;
				elapsed = h > 0
					? `${h}h ${m}m ${s}s`
					: m > 0
						? `${m}m ${s}s`
						: `${s}s`;
			};
			updateElapsed();
			interval = setInterval(updateElapsed, 1000);
		} else {
			elapsed = '';
		}
		return () => { if (interval) clearInterval(interval); };
	});

	function truncateId(id: string | null | undefined): string {
		if (!id) return '';
		return id.length > 12 ? id.slice(0, 12) + '...' : id;
	}

	const statusColor: Record<string, string> = {
		connected: '#22c55e',
		reconnecting: '#EE9B00',
		disconnected: '#ef4444'
	};

	const statusLabel: Record<string, string> = {
		connected: 'Connected',
		reconnecting: 'Reconnecting',
		disconnected: 'Disconnected'
	};
</script>

<header
	class="flex items-center justify-between px-4 border-b"
	style="height: 48px; background: var(--color-surface); border-color: var(--color-border);"
>
	<div class="flex items-center gap-3">
		<span class="font-semibold text-sm tracking-wide" style="color: var(--color-primary);">
			CC Observer
		</span>
	</div>

	<div class="flex items-center gap-3 text-xs" style="color: var(--color-text-muted);">
		{#if $activeSession}
			<span class="font-mono" style="color: var(--color-text);">
				{truncateId($activeSession.session_id)}
			</span>
			<span>{$activeSession.cwd}</span>
			{#if elapsed}
				<span style="color: var(--color-primary);">{elapsed}</span>
			{/if}
		{:else}
			<span>No active session</span>
		{/if}
	</div>

	<div class="flex items-center gap-3">
		{#if $connectionStatus === 'disconnected'}
			<button
				onclick={() => retrySSE()}
				class="text-xs px-2 py-1 rounded cursor-pointer border-none"
				style="background: var(--color-surface-2); color: var(--color-text);"
			>
				Retry
			</button>
		{/if}
		<div class="flex items-center gap-1.5 text-xs">
			<span
				class="inline-block w-2 h-2 rounded-full"
				style="background: {statusColor[$connectionStatus]}; {$connectionStatus === 'reconnecting' ? 'animation: pulse-dot 1.5s ease-in-out infinite;' : ''}"
			></span>
			<span style="color: var(--color-text-muted);">
				{statusLabel[$connectionStatus]}
				{#if $connectionStatus === 'reconnecting' && $reconnectAttempt > 0}
					({$reconnectAttempt})
				{/if}
			</span>
		</div>
		{#if $agentCount.active > 0}
			<span
				class="text-xs px-1.5 py-0.5 rounded-full font-medium"
				style="background: var(--color-primary); color: white;"
			>
				{$agentCount.active}
			</span>
		{/if}
	</div>
</header>
