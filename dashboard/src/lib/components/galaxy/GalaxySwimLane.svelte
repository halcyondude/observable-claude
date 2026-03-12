<script lang="ts">
	import type { SessionInfo } from '$lib/types/events';
	import type { WorkspaceGroup } from '$lib/stores/workspace';
	import { collapsedWorkspaces, toggleWorkspaceCollapse } from '$lib/stores/workspace';
	import GalaxySessionBar from './GalaxySessionBar.svelte';

	let {
		workspace,
		timeStart,
		timeEnd,
		selectedSessionId,
		onSelectSession
	}: {
		workspace: WorkspaceGroup;
		timeStart: number;
		timeEnd: number;
		selectedSessionId: string | null;
		onSelectSession: (id: string) => void;
	} = $props();

	const isCollapsed = $derived($collapsedWorkspaces.has(workspace.workspace));

	// Filter sessions that overlap with the time range
	const visibleSessions = $derived(
		workspace.sessions.filter((s) => {
			const start = new Date(s.start_time).getTime();
			const end = s.end_time ? new Date(s.end_time).getTime() : Date.now();
			return start < timeEnd && end > timeStart;
		}).sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
	);

	const name = $derived(workspace.name);
	const fullPath = $derived(workspace.workspace);
</script>

<div
	class="border-b"
	style="border-color: var(--color-border);"
>
	<!-- Lane header -->
	<button
		class="flex items-center gap-2 w-full px-4 py-2 text-left cursor-pointer border-none"
		style="background: var(--color-surface); height: 32px;"
		onclick={() => toggleWorkspaceCollapse(workspace.workspace)}
		title={fullPath}
	>
		<span
			class="text-xs transition-transform"
			style="color: var(--color-text-muted); transform: rotate({isCollapsed ? '0deg' : '90deg'});"
		>&#9654;</span>
		<span class="text-sm font-semibold" style="color: var(--color-text);">
			{name}
		</span>
		<span class="text-xs" style="color: var(--color-text-muted);">
			{workspace.active_count > 0 ? `${workspace.active_count} active` : ''}{workspace.active_count > 0 ? ' \u00b7 ' : ''}{workspace.total_count} total
		</span>
	</button>

	<!-- Lane body -->
	{#if !isCollapsed}
		<div class="relative px-4 py-1" style="min-height: 40px;">
			{#if visibleSessions.length === 0}
				<div class="text-xs py-2" style="color: var(--color-text-muted);">
					No sessions in selected time range
				</div>
			{:else}
				{#each visibleSessions as session, i}
					<div class="relative" style="height: {Math.min(40, 24 + (session.agent_count ?? 0) * 2) + 4}px;">
						<GalaxySessionBar
							{session}
							{timeStart}
							{timeEnd}
							isSelected={selectedSessionId === session.session_id}
							onclick={() => onSelectSession(session.session_id)}
						/>
					</div>
				{/each}
			{/if}
		</div>
	{:else}
		<!-- Collapsed mini-preview: tiny colored segments -->
		<div class="flex items-center gap-0.5 px-4 py-1" style="height: 8px;">
			{#each workspace.sessions.slice(0, 20) as session}
				{@const isActive = session.is_active}
				<div
					class="rounded-sm"
					style="
						width: {Math.max(4, Math.min(24, 100 / workspace.sessions.length))}px;
						height: 4px;
						background: {isActive ? 'var(--color-primary)' : 'var(--color-surface-2)'};
					"
				></div>
			{/each}
		</div>
	{/if}
</div>
