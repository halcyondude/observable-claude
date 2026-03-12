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
		collapsedWorkspaces,
		toggleWorkspaceCollapse,
		focusedLaneIndex,
		focusedBarIndex,
		recencyPreset,
		presetToSince,
		totalSessionCount,
		getWorkspaceColor
	} from '$lib/stores/workspace';
	import type { ActivityData, WorkspaceGroup, RecencyPreset } from '$lib/stores/workspace';
	import { activeSessionId } from '$lib/stores/session';
	import { fetchGroupedSessions, fetchActivity } from '$lib/services/api';
	import { events } from '$lib/stores/events';

	let activity = $state<ActivityData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;
	let windowWidth = $state(typeof window !== 'undefined' ? window.innerWidth : 1200);

	const presetOptions: { value: RecencyPreset; label: string }[] = [
		{ value: '1h', label: '1h' },
		{ value: '4h', label: '4h' },
		{ value: '24h', label: '24h' },
		{ value: '7d', label: '7d' },
		{ value: 'all', label: 'All' }
	];

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

	const isNarrow = $derived(windowWidth < 900);

	/** Build a flat list of navigable session bars for keyboard nav */
	const flatSessions = $derived(() => {
		const result: { laneIdx: number; barIdx: number; sessionId: string; workspace: string }[] = [];
		$sortedWorkspaces.forEach((ws, laneIdx) => {
			if ($collapsedWorkspaces.has(ws.workspace)) return;
			const visible = ws.sessions
				.filter((s) => {
					const start = new Date(s.start_time).getTime();
					const end = s.end_time ? new Date(s.end_time).getTime() : Date.now();
					return start < timeEnd && end > timeStart;
				})
				.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
			visible.forEach((s, barIdx) => {
				result.push({ laneIdx, barIdx, sessionId: s.session_id, workspace: ws.workspace });
			});
		});
		return result;
	});

	async function loadData() {
		try {
			const since = presetToSince($recencyPreset);
			const [grouped, act] = await Promise.all([
				fetchGroupedSessions(since),
				fetchActivity(since)
			]);
			workspaces.set(grouped);
			activity = act;
			error = null;

			// Single-session redirect: if only 1 session total, go to Spawn Tree
			if (!loading && grouped.length > 0) {
				const total = grouped.reduce((sum, ws) => sum + ws.sessions.length, 0);
				if (total === 1) {
					const onlySession = grouped[0].sessions[0];
					activeSessionId.set(onlySession.session_id);
					goto(`/tree?session=${onlySession.session_id}`);
					return;
				}
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load sessions';
		} finally {
			loading = false;
		}
	}

	function handleSelectSession(sessionId: string) {
		selectedGalaxySessionId.set(sessionId);
		// Also update keyboard focus to match
		const flat = flatSessions();
		const idx = flat.findIndex((f) => f.sessionId === sessionId);
		if (idx >= 0) {
			focusedLaneIndex.set(flat[idx].laneIdx);
			focusedBarIndex.set(flat[idx].barIdx);
		}
	}

	function handleCloseDetail() {
		selectedGalaxySessionId.set(null);
	}

	function handlePresetChange(preset: RecencyPreset) {
		recencyPreset.set(preset);
		loading = true;
		loadData();
	}

	function resetToAll() {
		handlePresetChange('all');
	}

	function handleKeydown(e: KeyboardEvent) {
		// Don't capture if user is typing in an input
		if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

		const flat = flatSessions();
		const currentFocusLane = $focusedLaneIndex;
		const currentFocusBar = $focusedBarIndex;

		// Find current position in flat list
		let currentFlatIdx = flat.findIndex(
			(f) => f.laneIdx === currentFocusLane && f.barIdx === currentFocusBar
		);

		if (e.key === 'Escape') {
			handleCloseDetail();
			return;
		}

		if (e.key === 'ArrowDown') {
			e.preventDefault();
			// Move to next lane's first bar
			const nextLane = currentFocusLane + 1;
			const nextInLane = flat.find((f) => f.laneIdx === nextLane);
			if (nextInLane) {
				focusedLaneIndex.set(nextInLane.laneIdx);
				focusedBarIndex.set(nextInLane.barIdx);
				selectedGalaxySessionId.set(nextInLane.sessionId);
			}
			return;
		}

		if (e.key === 'ArrowUp') {
			e.preventDefault();
			// Move to previous lane's first bar
			const prevLane = currentFocusLane - 1;
			const prevInLane = flat.find((f) => f.laneIdx === prevLane);
			if (prevInLane) {
				focusedLaneIndex.set(prevInLane.laneIdx);
				focusedBarIndex.set(prevInLane.barIdx);
				selectedGalaxySessionId.set(prevInLane.sessionId);
			} else if (currentFocusLane === -1 && flat.length > 0) {
				// First focus
				focusedLaneIndex.set(flat[0].laneIdx);
				focusedBarIndex.set(flat[0].barIdx);
				selectedGalaxySessionId.set(flat[0].sessionId);
			}
			return;
		}

		if (e.key === 'ArrowRight') {
			e.preventDefault();
			// Next bar within same lane
			const nextInLane = flat.find(
				(f) => f.laneIdx === currentFocusLane && f.barIdx === currentFocusBar + 1
			);
			if (nextInLane) {
				focusedBarIndex.set(nextInLane.barIdx);
				selectedGalaxySessionId.set(nextInLane.sessionId);
			}
			return;
		}

		if (e.key === 'ArrowLeft') {
			e.preventDefault();
			// Previous bar within same lane
			if (currentFocusBar > 0) {
				const prevInLane = flat.find(
					(f) => f.laneIdx === currentFocusLane && f.barIdx === currentFocusBar - 1
				);
				if (prevInLane) {
					focusedBarIndex.set(prevInLane.barIdx);
					selectedGalaxySessionId.set(prevInLane.sessionId);
				}
			}
			return;
		}

		if (e.key === 'Enter') {
			if ($selectedGalaxySessionId) {
				// If detail panel is already open, navigate to Spawn Tree
				activeSessionId.set($selectedGalaxySessionId);
				goto(`/tree?session=${$selectedGalaxySessionId}`);
			}
			return;
		}

		if (e.key === '[') {
			// Collapse focused workspace lane
			if (currentFocusLane >= 0 && currentFocusLane < $sortedWorkspaces.length) {
				const ws = $sortedWorkspaces[currentFocusLane];
				if (!$collapsedWorkspaces.has(ws.workspace)) {
					toggleWorkspaceCollapse(ws.workspace);
				}
			}
			return;
		}

		if (e.key === ']') {
			// Expand focused workspace lane
			if (currentFocusLane >= 0 && currentFocusLane < $sortedWorkspaces.length) {
				const ws = $sortedWorkspaces[currentFocusLane];
				if ($collapsedWorkspaces.has(ws.workspace)) {
					toggleWorkspaceCollapse(ws.workspace);
				}
			}
			return;
		}
	}

	// Refresh data when new SSE events arrive
	let lastEventCount = 0;
	$effect(() => {
		const evts = $events;
		if (evts.length !== lastEventCount) {
			lastEventCount = evts.length;
			const latest = evts[0];
			if (
				latest &&
				(latest.event_type === 'SessionStart' || latest.event_type === 'SessionEnd')
			) {
				loadData();
			}
		}
	});

	function handleResize() {
		windowWidth = window.innerWidth;
	}

	onMount(() => {
		loadData();
		refreshInterval = setInterval(loadData, 30_000);
		window.addEventListener('keydown', handleKeydown);
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
		window.removeEventListener('keydown', handleKeydown);
		window.removeEventListener('resize', handleResize);
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
			<div class="rounded" style="height: {isNarrow ? 48 : 64}px; background: linear-gradient(90deg, var(--color-surface) 25%, var(--color-surface-2) 50%, var(--color-surface) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite;"></div>
			<!-- Lane skeletons with animated bars -->
			{#each [1, 2, 3] as n}
				<div>
					<div class="rounded mb-1" style="height: 32px; background: var(--color-surface); width: 200px;"></div>
					<div class="flex gap-2">
						{#each Array(Math.max(1, 4 - n)) as _}
							<div
								class="rounded"
								style="height: 32px; flex: 1; background: linear-gradient(90deg, var(--color-surface-2) 25%, var(--color-surface) 50%, var(--color-surface-2) 75%); background-size: 200% 100%; animation: shimmer 1.5s infinite; animation-delay: {n * 0.2}s;"
							></div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{:else if $sortedWorkspaces.length === 0 && $recencyPreset !== 'all'}
		<!-- No sessions in time range -->
		<div class="flex-1 flex items-center justify-center">
			<div class="text-center space-y-3">
				<div class="text-4xl opacity-20" style="color: var(--color-text-muted);">&#9737;</div>
				<div class="text-sm" style="color: var(--color-text-muted);">
					No sessions in this time window. Try expanding the range.
				</div>
				<button
					class="px-4 py-2 rounded text-xs font-medium cursor-pointer border-none"
					style="background: var(--color-primary); color: white;"
					onclick={resetToAll}
				>
					Show all sessions
				</button>
			</div>
		</div>
	{:else if $sortedWorkspaces.length === 0}
		<!-- Empty state: no sessions at all -->
		<div class="flex-1 flex items-center justify-center">
			<div class="text-center space-y-3">
				<div class="text-4xl opacity-20" style="color: var(--color-text-muted);">&#9737;</div>
				<div class="text-sm" style="color: var(--color-text-muted);">
					No sessions captured. Start using Claude Code with the observer plugin.
				</div>
			</div>
		</div>
	{:else}
		<!-- Recency preset selector + Time brush -->
		<div class="px-4 pt-3 pb-1" style="border-bottom: 1px solid var(--color-border);">
			<div class="flex items-center justify-between mb-2">
				<div class="flex items-center gap-1" role="radiogroup" aria-label="Time range">
					{#each presetOptions as opt}
						<button
							class="px-2.5 py-1 rounded text-xs font-medium cursor-pointer border-none"
							style="
								background: {$recencyPreset === opt.value ? 'var(--color-primary)' : 'var(--color-surface-2)'};
								color: {$recencyPreset === opt.value ? 'white' : 'var(--color-text-muted)'};
								transition: background 0.15s ease;
							"
							role="radio"
							aria-checked={$recencyPreset === opt.value}
							onclick={() => handlePresetChange(opt.value)}
						>
							{opt.label}
						</button>
					{/each}
				</div>
				<span class="text-xs" style="color: var(--color-text-muted);">
					{$totalSessionCount} session{$totalSessionCount !== 1 ? 's' : ''}
				</span>
			</div>

			<GalaxyTimeBrush
				{activity}
				workspaceColors={workspaceColorMap()}
				compact={isNarrow}
			/>
		</div>

		<!-- Swim lanes + detail panel wrapper -->
		<div class="flex flex-1 overflow-hidden relative">
			<!-- Swim lanes -->
			<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
			<div
				class="flex-1 overflow-y-auto"
				onclick={(e) => { if (e.target === e.currentTarget) handleCloseDetail(); }}
			>
				{#each $sortedWorkspaces as workspace, laneIdx (workspace.workspace)}
					<GalaxySwimLane
						{workspace}
						{timeStart}
						{timeEnd}
						selectedSessionId={$selectedGalaxySessionId}
						onSelectSession={handleSelectSession}
						isFocusedLane={$focusedLaneIndex === laneIdx}
						focusedBarIndex={$focusedLaneIndex === laneIdx ? $focusedBarIndex : -1}
						compact={isNarrow}
					/>
				{/each}
			</div>

			<!-- Detail panel -->
			{#if !isNarrow}
				<GalaxyDetailPanel
					session={selectedSession()}
					onclose={handleCloseDetail}
					mode="side"
				/>
			{/if}
		</div>

		<!-- Bottom sheet detail panel for narrow screens -->
		{#if isNarrow}
			<GalaxyDetailPanel
				session={selectedSession()}
				onclose={handleCloseDetail}
				mode="bottom"
			/>
		{/if}
	{/if}
</div>

<style>
	@keyframes shimmer {
		0% { background-position: 200% 0; }
		100% { background-position: -200% 0; }
	}
</style>
