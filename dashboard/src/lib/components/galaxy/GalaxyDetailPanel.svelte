<script lang="ts">
	import type { SessionInfo } from '$lib/types/events';
	import { goto } from '$app/navigation';
	import { sessionMessageCounts } from '$lib/stores/events';

	let {
		session,
		onclose,
		mode = 'side'
	}: {
		session: SessionInfo | null;
		onclose: () => void;
		mode?: 'side' | 'bottom';
	} = $props();

	function relativeTime(ts: string): string {
		const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
		if (diff < 60) return `${diff}s ago`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s ago`;
		return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m ago`;
	}

	function formatDuration(startMs: number, endMs: number): string {
		const s = Math.floor((endMs - startMs) / 1000);
		if (s < 60) return `${s}s`;
		if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
		return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
	}

	const startMs = $derived(session ? new Date(session.start_time).getTime() : 0);
	const endMs = $derived(
		session?.end_time ? new Date(session.end_time).getTime() : Date.now()
	);
	const duration = $derived(formatDuration(startMs, endMs));

	$effect(() => {
		function handleClose() { onclose(); }
		document.addEventListener('close-panels', handleClose);
		return () => document.removeEventListener('close-panels', handleClose);
	});

	// Live duration ticker
	let liveDuration = $state('');
	let tickInterval: ReturnType<typeof setInterval> | null = null;

	$effect(() => {
		if (tickInterval) clearInterval(tickInterval);
		if (session?.is_active) {
			function tick() {
				liveDuration = formatDuration(startMs, Date.now());
			}
			tick();
			tickInterval = setInterval(tick, 1000);
		} else {
			liveDuration = duration;
		}
		return () => {
			if (tickInterval) clearInterval(tickInterval);
		};
	});
</script>

{#if session}
	{#if mode === 'side'}
		<!-- Side panel (desktop) -->
		<div
			class="fixed top-12 right-0 bottom-0 overflow-y-auto z-50 border-l"
			style="width: 320px; background: var(--color-surface); border-color: var(--color-border); animation: slideInRight 0.2s ease-out;"
		>
			{@render panelContent()}
		</div>
	{:else}
		<!-- Bottom sheet (mobile/narrow) -->
		<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions a11y_no_noninteractive_element_interactions -->
		<div
			class="fixed inset-0 z-40"
			style="background: rgba(0,0,0,0.4);"
			onclick={onclose}
		></div>
		<div
			class="fixed left-0 right-0 bottom-0 z-50 overflow-y-auto border-t rounded-t-lg"
			style="height: 50vh; background: var(--color-surface); border-color: var(--color-border); animation: slideInUp 0.2s ease-out;"
		>
			<!-- Drag handle indicator -->
			<div class="flex justify-center pt-2 pb-1">
				<div class="rounded-full" style="width: 32px; height: 4px; background: var(--color-text-muted); opacity: 0.4;"></div>
			</div>
			{@render panelContent()}
		</div>
	{/if}
{/if}

{#snippet panelContent()}
	<div class="p-4">
		<div class="flex items-center justify-between mb-4">
			<h3 class="text-sm font-semibold" style="color: var(--color-text);">Session Detail</h3>
			<button
				onclick={onclose}
				class="text-sm cursor-pointer border-none"
				style="background: transparent; color: var(--color-text-muted);"
			>&times;</button>
		</div>

		<div class="space-y-3 text-xs">
			<!-- Session ID -->
			<div>
				<span style="color: var(--color-text-muted);">Session ID</span>
				<div class="font-mono mt-0.5 break-all">{session!.session_id}</div>
			</div>

			<!-- Status -->
			<div>
				<span style="color: var(--color-text-muted);">Status</span>
				<div class="mt-0.5">
					{#if session!.is_active}
						<span
							class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium"
							style="background: var(--color-primary); color: white;"
						>
							<span
								class="inline-block w-1.5 h-1.5 rounded-full"
								style="background: white; animation: pulse-dot 2s ease-in-out infinite;"
							></span>
							LIVE
						</span>
					{:else}
						<span
							class="inline-block px-2 py-0.5 rounded text-xs font-medium"
							style="background: var(--color-surface-2); color: var(--color-text-muted);"
						>
							complete
						</span>
					{/if}
				</div>
			</div>

			<!-- Workspace -->
			<div>
				<span style="color: var(--color-text-muted);">Workspace</span>
				<div class="mt-0.5">{session!.cwd}</div>
			</div>

			<!-- Branch -->
			{#if (session as any).branch}
				<div>
					<span style="color: var(--color-text-muted);">Branch</span>
					<div class="mt-0.5 font-mono">{(session as any).branch}</div>
				</div>
			{/if}

			<!-- Timing -->
			<div>
				<span style="color: var(--color-text-muted);">Started</span>
				<div class="mt-0.5">
					{new Date(session!.start_time).toLocaleTimeString()}
					<span style="color: var(--color-text-muted);"> ({relativeTime(session!.start_time)})</span>
				</div>
			</div>

			<div>
				<span style="color: var(--color-text-muted);">Duration</span>
				<div class="mt-0.5">
					{session!.is_active ? liveDuration : duration}
				</div>
			</div>

			<!-- Counts -->
			<div class="flex gap-6">
				<div>
					<span style="color: var(--color-text-muted);">Agents</span>
					<div class="mt-0.5 text-lg font-semibold">{session!.agent_count}</div>
				</div>
				<div>
					<span style="color: var(--color-text-muted);">Events</span>
					<div class="mt-0.5 text-lg font-semibold">{session!.event_count}</div>
				</div>
				<div>
					<span style="color: var(--color-text-muted);">Messages</span>
					<div class="mt-0.5 text-lg font-semibold">{$sessionMessageCounts[session!.session_id] ?? 0}</div>
				</div>
			</div>

			<!-- Mini spawn tree placeholder -->
			<div>
				<span style="color: var(--color-text-muted);">Spawn Tree</span>
				<div
					class="mt-1 p-2 rounded text-xs"
					style="background: var(--color-bg); min-height: 60px; color: var(--color-text-muted);"
				>
					{#if session!.agent_count > 0}
						<div class="flex items-center gap-1">
							<span style="color: var(--color-primary);">&#9679;</span>
							<span class="font-mono">session</span>
						</div>
						{#each Array(Math.min(session!.agent_count, 6)) as _, i}
							<div class="flex items-center gap-1" style="padding-left: {(i % 3 + 1) * 12}px;">
								<span style="color: var(--color-primary); opacity: {1 - i * 0.1};">&#9679;</span>
								<span class="font-mono">agent-{i + 1}</span>
							</div>
						{/each}
						{#if session!.agent_count > 6}
							<div style="padding-left: 12px; color: var(--color-text-muted);">
								... {session!.agent_count - 6} more
							</div>
						{/if}
					{:else}
						<span>No subagents</span>
					{/if}
				</div>
			</div>

			<!-- Action buttons -->
			<div class="flex flex-wrap gap-2 pt-2">
				<button
					class="flex-1 py-2 px-3 rounded text-xs font-medium cursor-pointer border-none"
					style="background: var(--color-primary); color: white;"
					onclick={() => goto(`/tree?session=${session!.session_id}`)}
				>
					Open Spawn Tree
				</button>
				<button
					class="flex-1 py-2 px-3 rounded text-xs font-medium cursor-pointer border-none"
					style="background: var(--color-surface-2); color: var(--color-text);"
					onclick={() => goto(`/timeline?session=${session!.session_id}`)}
				>
					Open Timeline
				</button>
				{#if ($sessionMessageCounts[session!.session_id] ?? 0) > 0}
					<button
						class="flex-1 py-2 px-3 rounded text-xs font-medium cursor-pointer border-none"
						style="background: var(--color-surface-2); color: var(--color-text);"
						onclick={() => goto(`/sessions?session=${session!.session_id}&tab=conversation`)}
					>
						Open Conversation
					</button>
				{/if}
			</div>
		</div>
	</div>
{/snippet}

<style>
	@keyframes slideInRight {
		from { transform: translateX(320px); }
		to { transform: translateX(0); }
	}
	@keyframes slideInUp {
		from { transform: translateY(50vh); }
		to { transform: translateY(0); }
	}
</style>
