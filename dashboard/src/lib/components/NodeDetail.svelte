<script lang="ts">
	import type { GraphNode } from '$lib/types/events';
	import ToolStrip from './ToolStrip.svelte';
	import ToolFamilyBar from './ToolFamilyBar.svelte';
	import { getToolColor } from '$lib/stores/tool-families';

	let {
		node,
		onclose,
		toolCalls = []
	}: {
		node: GraphNode | null;
		onclose: () => void;
		toolCalls?: Array<{ name: string; status: string; duration_ms?: number }>;
	} = $props();

	function relativeTime(ts?: string): string {
		if (!ts) return '';
		const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
		if (diff < 60) return `${diff}s ago`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s ago`;
		return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m ago`;
	}

	const statusStyles: Record<string, { bg: string; text: string }> = {
		running: { bg: 'var(--color-primary)', text: 'white' },
		complete: { bg: 'var(--color-surface-2)', text: 'var(--color-text-muted)' },
		failed: { bg: 'var(--color-error)', text: 'white' }
	};

	// Build tool call list from node.data.tools when no explicit toolCalls provided
	const effectiveToolCalls = $derived.by(() => {
		if (toolCalls.length > 0) return toolCalls;
		if (!node?.data.tools) return [];
		// Expand the name->count map into individual entries for ToolStrip/ToolFamilyBar
		const calls: Array<{ name: string; status: string }> = [];
		for (const [name, count] of Object.entries(node.data.tools)) {
			for (let i = 0; i < (count as number); i++) {
				calls.push({ name, status: 'success' });
			}
		}
		return calls;
	});

	$effect(() => {
		function handleClose() { onclose(); }
		document.addEventListener('close-panels', handleClose);
		return () => document.removeEventListener('close-panels', handleClose);
	});
</script>

{#if node}
	<div
		class="fixed top-12 right-0 bottom-0 overflow-y-auto z-50 border-l"
		style="width: 320px; background: var(--color-surface); border-color: var(--color-border);"
	>
		<div class="p-4">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-sm font-semibold">{node.data.agent_type}</h3>
				<button
					onclick={onclose}
					class="text-sm cursor-pointer border-none"
					style="background: transparent; color: var(--color-text-muted);"
				>&times;</button>
			</div>

			<div class="space-y-3 text-xs">
				<div>
					<span style="color: var(--color-text-muted);">Agent ID</span>
					<div class="font-mono mt-0.5 break-all">{node.data.id}</div>
				</div>

				<div>
					<span style="color: var(--color-text-muted);">Status</span>
					<div class="mt-0.5">
						{#if true}
							{@const style = statusStyles[node.data.status] ?? statusStyles.complete}
							<span
								class="inline-block px-2 py-0.5 rounded text-xs font-medium"
								style="background: {style.bg}; color: {style.text};"
							>
								{node.data.status}
							</span>
						{/if}
					</div>
				</div>

				{#if node.data.started_at}
					<div>
						<span style="color: var(--color-text-muted);">Started</span>
						<div class="mt-0.5">
							{new Date(node.data.started_at).toLocaleTimeString()}
							<span style="color: var(--color-text-muted);"> ({relativeTime(node.data.started_at)})</span>
						</div>
					</div>
				{/if}

				{#if node.data.spawned_by}
					<div>
						<span style="color: var(--color-text-muted);">Spawned by</span>
						<div class="font-mono mt-0.5">{node.data.spawned_by}</div>
					</div>
				{/if}

				{#if node.data.prompt}
					<div>
						<span style="color: var(--color-text-muted);">Prompt</span>
						<div
							class="mt-1 p-2 rounded text-xs overflow-y-auto"
							style="background: var(--color-bg); max-height: 200px; white-space: pre-wrap;"
						>{node.data.prompt}</div>
					</div>
				{/if}

				{#if effectiveToolCalls.length > 0}
					<div>
						<span style="color: var(--color-text-muted);">Tool Activity ({node.data.tool_count})</span>

						<!-- Tool Strip — chronological pip sequence -->
						<div class="mt-1.5">
							<ToolStrip toolCalls={effectiveToolCalls} />
						</div>

						<!-- Family breakdown bar -->
						<div class="mt-1.5">
							<ToolFamilyBar toolCalls={effectiveToolCalls} height={10} />
						</div>

						<!-- Tool count list with family color dots -->
						{#if node.data.tools && Object.keys(node.data.tools).length > 0}
							<div class="mt-2 space-y-1">
								{#each Object.entries(node.data.tools) as [name, count]}
									<div class="flex items-center justify-between">
										<div class="flex items-center gap-1.5">
											<span
												class="inline-block rounded-full flex-shrink-0"
												style="width: 6px; height: 6px; background: {getToolColor(name)};"
											></span>
											<span class="font-mono">{name}</span>
										</div>
										<span style="color: var(--color-text-muted);">{count}</span>
									</div>
								{/each}
							</div>
						{/if}

						<!-- View in Tool Feed link -->
						<div class="mt-2">
							<a
								href="/tools?agent={node.data.id}"
								class="inline-flex items-center gap-1 text-xs no-underline"
								style="color: var(--color-primary);"
							>
								View in Tool Feed
								<span style="font-size: 10px;">&#8594;</span>
							</a>
						</div>
					</div>
				{:else if node.data.tools && Object.keys(node.data.tools).length > 0}
					<!-- Fallback: plain tool list when no tool call data available -->
					<div>
						<span style="color: var(--color-text-muted);">Tools ({node.data.tool_count})</span>
						<div class="mt-1 space-y-1">
							{#each Object.entries(node.data.tools) as [name, count]}
								<div class="flex items-center justify-between">
									<div class="flex items-center gap-1.5">
										<span
											class="inline-block rounded-full flex-shrink-0"
											style="width: 6px; height: 6px; background: {getToolColor(name)};"
										></span>
										<span class="font-mono">{name}</span>
									</div>
									<span style="color: var(--color-text-muted);">{count}</span>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				{#if node.data.skills && node.data.skills.length > 0}
					<div>
						<span style="color: var(--color-text-muted);">Skills</span>
						<div class="mt-1 flex flex-wrap gap-1">
							{#each node.data.skills as skill}
								<span
									class="px-1.5 py-0.5 rounded text-xs"
									style="background: var(--color-surface-2);"
								>{skill}</span>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}
