<script lang="ts">
	import { onMount } from 'svelte';
	import { sessions, activeSessionId, liveSessionId, switchToSession } from '$lib/stores/session';
	import { isReplaying, startReplay as startReplayStore } from '$lib/stores/replay';
	import { fetchSessions } from '$lib/services/api';
	import { connectReplay } from '$lib/services/sse';
	import type { SessionInfo } from '$lib/types/events';

	function handleReplay(session: SessionInfo) {
		startReplayStore(session.session_id);
		switchToSession(session.session_id);
		connectReplay(session.session_id, 1);
	}

	let sessionList = $state<SessionInfo[]>([]);
	let loadError = $state<string | null>(null);

	async function loadSessions() {
		try {
			sessionList = await fetchSessions();
			sessions.set(sessionList);
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to load sessions';
		}
	}

	onMount(() => {
		loadSessions();
		const interval = setInterval(loadSessions, 10_000);
		return () => clearInterval(interval);
	});

	function formatDuration(start: string, end?: string): string {
		const startMs = new Date(start).getTime();
		const endMs = end ? new Date(end).getTime() : Date.now();
		const diff = Math.floor((endMs - startMs) / 1000);
		if (diff < 60) return `${diff}s`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s`;
		return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`;
	}

	function formatTime(ts: string): string {
		return new Date(ts).toLocaleString();
	}

	function lastPathSegment(cwd: string): string {
		const parts = cwd.split('/').filter(Boolean);
		return parts[parts.length - 1] ?? cwd;
	}

	function selectSession(s: SessionInfo) {
		switchToSession(s.session_id);
	}
</script>

<div class="flex h-full">
	<!-- Session list -->
	<div
		class="overflow-y-auto border-r"
		style="width: 320px; background: var(--color-surface); border-color: var(--color-border);"
	>
		{#if loadError}
			<div class="p-4 text-xs" style="color: var(--color-error);">{loadError}</div>
		{/if}

		{#if sessionList.length === 0 && !loadError}
			<div class="p-4 text-xs" style="color: var(--color-text-muted);">
				No sessions found
			</div>
		{/if}

		{#each sessionList as session}
			{@const isLive = session.session_id === $liveSessionId}
			{@const isSelected = session.session_id === $activeSessionId}
			<button
				onclick={() => selectSession(session)}
				class="w-full text-left p-3 border-b cursor-pointer border-none"
				style="background: {isSelected ? 'rgba(10, 147, 150, 0.1)' : 'transparent'}; border-left: 3px solid {isLive ? 'var(--color-primary)' : 'transparent'}; border-bottom: 1px solid var(--color-border);"
			>
				<div class="flex items-center gap-2 mb-1">
					<span
						class="w-2 h-2 rounded-full inline-block"
						style="background: {session.is_active ? '#22c55e' : 'var(--color-text-muted)'};"
					></span>
					<span class="text-sm font-semibold" style="color: var(--color-text);">
						{lastPathSegment(session.cwd)}
					</span>
					{#if isLive}
						<span
							class="px-1.5 py-0.5 rounded text-xs font-medium"
							style="background: var(--color-primary); color: white; font-size: 9px;"
						>LIVE</span>
					{/if}
				</div>

				<div class="text-xs truncate" style="color: var(--color-text-muted);">
					{session.cwd}
				</div>

				<div class="flex gap-3 mt-1.5 text-xs" style="color: var(--color-text-muted);">
					<span>{formatTime(session.start_time)}</span>
					<span>{formatDuration(session.start_time, session.end_time)}</span>
				</div>

				<div class="flex gap-3 mt-1 text-xs items-center" style="color: var(--color-text-muted);">
					<span>{session.agent_count} agents</span>
					<span>{session.event_count} events</span>
					{#if !session.is_active}
						<span
							role="button"
							tabindex="0"
							onclick={(e) => { e.stopPropagation(); handleReplay(session); }}
							onkeydown={(e) => { if (e.key === 'Enter') { e.stopPropagation(); handleReplay(session); } }}
							class="ml-auto px-2 py-0.5 rounded text-xs cursor-pointer"
							style="background: var(--color-surface-2); color: var(--color-primary);"
							title="Replay session"
						>
							Replay
						</span>
					{/if}
				</div>
			</button>
		{/each}
	</div>

	<!-- Session detail -->
	<div class="flex-1 flex items-center justify-center" style="background: var(--color-bg);">
		{#if $activeSessionId}
			{@const session = sessionList.find((s) => s.session_id === $activeSessionId)}
			{#if session}
				<div class="text-center space-y-3">
					<div class="text-lg font-semibold">{lastPathSegment(session.cwd)}</div>
					<div class="font-mono text-xs" style="color: var(--color-text-muted);">{session.session_id}</div>
					<div class="flex gap-6 justify-center text-sm" style="color: var(--color-text-muted);">
						<div>
							<div class="text-xl font-bold" style="color: var(--color-text);">{session.agent_count}</div>
							<div>agents</div>
						</div>
						<div>
							<div class="text-xl font-bold" style="color: var(--color-text);">{session.event_count}</div>
							<div>events</div>
						</div>
						<div>
							<div class="text-xl font-bold" style="color: var(--color-text);">
								{formatDuration(session.start_time, session.end_time)}
							</div>
							<div>duration</div>
						</div>
					</div>
					{#if !session.is_active}
						<button
							onclick={() => handleReplay(session)}
							class="mt-2 px-4 py-2 rounded-lg text-sm font-medium cursor-pointer border-none"
							style="background: var(--color-primary); color: white;"
						>
							Replay Session
						</button>
					{/if}
					<div class="text-xs mt-2" style="color: var(--color-text-muted);">
						Select a view from the sidebar to explore this session's data
					</div>
				</div>
			{/if}
		{:else}
			<div class="text-sm" style="color: var(--color-text-muted);">
				Select a session to view details
			</div>
		{/if}
	</div>
</div>
