<script lang="ts">
	import type { GraphNode } from '$lib/types/events';
	import ConversationPanel from './ConversationPanel.svelte';

	let { node, onclose }: { node: GraphNode | null; onclose: () => void } = $props();

	let activeTab = $state<'details' | 'conversation'>('details');

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

	// Reset to details tab when a different node is selected
	$effect(() => {
		if (node) {
			activeTab = 'details';
		}
	});

	$effect(() => {
		function handleClose() { onclose(); }
		document.addEventListener('close-panels', handleClose);
		return () => document.removeEventListener('close-panels', handleClose);
	});
</script>

{#if node}
	<div
		class="fixed top-12 right-0 bottom-0 flex flex-col z-50 border-l"
		style="width: 320px; background: var(--color-surface); border-color: var(--color-border);"
	>
		<!-- Header -->
		<div class="px-4 pt-4 pb-0">
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-sm font-semibold">{node.data.agent_type}</h3>
				<button
					onclick={onclose}
					class="text-sm cursor-pointer border-none"
					style="background: transparent; color: var(--color-text-muted);"
				>&times;</button>
			</div>

			<!-- Tab navigation -->
			<div class="flex border-b" style="border-color: var(--color-border);">
				<button
					onclick={() => activeTab = 'details'}
					class="px-3 py-2 text-xs cursor-pointer border-none"
					style="background: transparent;
						color: {activeTab === 'details' ? 'var(--color-text)' : 'var(--color-text-muted)'};
						border-bottom: 2px solid {activeTab === 'details' ? 'var(--color-primary)' : 'transparent'};
						margin-bottom: -1px;"
				>Details</button>
				<button
					onclick={() => activeTab = 'conversation'}
					class="px-3 py-2 text-xs cursor-pointer border-none"
					style="background: transparent;
						color: {activeTab === 'conversation' ? 'var(--color-text)' : 'var(--color-text-muted)'};
						border-bottom: 2px solid {activeTab === 'conversation' ? 'var(--color-primary)' : 'transparent'};
						margin-bottom: -1px;"
				>Conversation</button>
			</div>
		</div>

		<!-- Tab content -->
		{#if activeTab === 'details'}
			<div class="flex-1 overflow-y-auto p-4">
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

					{#if node.data.tools && Object.keys(node.data.tools).length > 0}
						<div>
							<span style="color: var(--color-text-muted);">Tools ({node.data.tool_count})</span>
							<div class="mt-1 space-y-1">
								{#each Object.entries(node.data.tools) as [name, count]}
									<div class="flex justify-between">
										<span class="font-mono">{name}</span>
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
		{:else}
			<div class="flex-1 overflow-hidden">
				<ConversationPanel agentId={node.data.id} />
			</div>
		{/if}
	</div>
{/if}
