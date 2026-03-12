<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import GalaxyTimeBrush from '$lib/components/galaxy/GalaxyTimeBrush.svelte';
	import GalaxySwimLane from '$lib/components/galaxy/GalaxySwimLane.svelte';
	import GalaxyDetailPanel from '$lib/components/galaxy/GalaxyDetailPanel.svelte';
	import {
		workspaces,
		sortedWorkspaces,
		selectedGalaxySessionId,
		timeRange,
		getWorkspaceColor
	} from '$lib/stores/workspace';
	import type { ActivityData, WorkspaceGroup } from '$lib/stores/workspace';
	import { activeSessionId } from '$lib/stores/session';
	import { fetchGroupedSessions, fetchActivity } from '$lib/services/api';
	import { events } from '$lib/stores/events';

	let activity = $state<ActivityData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	const workspaceColorMap = $derived(() => {
		const map = new Map<string, string>();
		$sortedWorkspaces.forEach((ws, i) => {
			map.set(ws.workspace, getWorkspaceColor(i));
		});
		return map;
	});

	const currentTimeRange = $derived($timeRange);

	const timeStart = $derived(currentTimeRange?.start ?? Date.now() - 4 * 60 * 60 * 1000);
	const timeEnd = $derived(currentTimeRange?.end ?? Date.now());

	const selectedSession = $derived(() => {
		const sid = $selectedGalaxySessionId;
		if (!sid) return null;
		for (const ws of $sortedWorkspaces) {
			const found = ws.sessions.find((s) => s.session_id === sid);
			if (found) return found;
		}
		return null;
	});

	async function loadData() {
		try {
			const [grouped, act] = await Promise.all([
				fetchGroupedSessions(),
				fetchActivity()
			]);
			workspaces.set(grouped);
			activity = act;
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load sessions';
		} finally {
			loading = false;
		}
	}

	function handleSelectSession(sessionId: string) {
		selectedGalaxySessionId.set(sessionId);
	}

	function handleCloseDetail() {
		selectedGalaxySessionId.set(null);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			handleCloseDetail();
		}
		if (e.key === 'Enter' && $selectedGalaxySessionId) {
			activeSessionId.set($selectedGalaxySessionId);
			goto(`/tree?session=${$selectedGalaxySessionId}`);
		}
	}

	// Refresh data when new SSE events arrive
	let lastEventCount = 0;
	$effect(() => {
		const evts = $events;
		if (evts.length !== lastEventCount) {
			lastEventCount = evts.length;
			// Debounce: only refresh on session lifecycle events
			const latest = evts[0];
			if (
				latest &&
				(latest.event_type === 'SessionStart' || latest.event_type === 'SessionEnd')
			) {
				loadData();
			}
		}
	});

	onMount(() => {
		loadData();
		// Periodic refresh for activity data
		refreshInterval = setInterval(loadData, 30_000);
		window.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
		window.removeEventListener('keydown', handleKeydown);
	});
</script>

<div class="flex flex-col h-full overflow-hidden">
	<!-- Error banner -->
	{#if error}
		<div
			class="flex items-center justify-between px-4 py-2 text-xs"
			style="background: var(--color-error); color: white;"
		>
			<span>Failed to load sessions: {error}</span>
			<button
				class="px-3 py-1 rounded text-xs cursor-pointer border-none"
				style="background: rgba(255,255,255,0.2); color: white;"
				onclick={loadData}
			>
				Retry
			</button>
		</div>
	{/if}

	{#if loading}
		<!-- Loading skeleton -->
		<div class="p-4 space-y-4">
			<!-- Time brush skeleton -->
			<div class="rounded" style="height: 64px; background: linear-gradient(90deg, var(--color-surface) 25%, var(--color-surface-2) 50%, var(--color-surface) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite;"></div>
			<!-- Lane skeletons -->
			{#each [1, 2, 3] as _}
				<div>
					<div class="rounded mb-1" style="height: 32px; background: var(--color-surface); width: 200px;"></div>
					<div class="rounded" style="height: 32px; background: var(--color-surface-2); width: 60%;"></div>
				</div>
			{/each}
		</div>
	{:else if $sortedWorkspaces.length === 0}
		<!-- Empty state -->
		<div class="flex-1 flex items-center justify-center">
			<div class="text-center space-y-3">
				<div class="text-4xl opacity-20" style="color: var(--color-text-muted);">&#9737;</div>
				<div class="text-sm" style="color: var(--color-text-muted);">
					No sessions observed. Start a Claude Code session to begin.
				</div>
			</div>
		</div>
	{:else}
		<!-- Time brush -->
		<div class="px-4 pt-3 pb-1" style="border-bottom: 1px solid var(--color-border);">
			<GalaxyTimeBrush
				{activity}
				workspaceColors={workspaceColorMap()}
			/>
		</div>

		<!-- Swim lanes -->
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
		<div class="flex-1 overflow-y-auto" onclick={(e) => { if (e.target === e.currentTarget) handleCloseDetail(); }}>
			{#each $sortedWorkspaces as workspace (workspace.workspace)}
				<GalaxySwimLane
					{workspace}
					{timeStart}
					{timeEnd}
					selectedSessionId={$selectedGalaxySessionId}
					onSelectSession={handleSelectSession}
				/>
			{/each}
		</div>

		<!-- Detail panel -->
		<GalaxyDetailPanel
			session={selectedSession()}
			onclose={handleCloseDetail}
		/>
	{/if}
</div>

<style>
	@keyframes shimmer {
		0% { background-position: 200% 0; }
		100% { background-position: -200% 0; }
	}
</style>
