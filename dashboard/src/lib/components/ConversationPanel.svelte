<script lang="ts">
	import type { AgentMessage } from '$lib/types/events';

	let {
		agent_id,
		onclose
	}: {
		agent_id: string | null;
		onclose: () => void;
	} = $props();

	let messages: AgentMessage[] = $state([]);
	let loading = $state(false);
	let error = $state('');

	const roleStyles: Record<string, { bg: string; text: string; align: string }> = {
		user: {
			bg: 'var(--color-surface-2)',
			text: 'var(--color-text)',
			align: 'left'
		},
		system: {
			bg: 'var(--color-surface-2)',
			text: 'var(--color-text)',
			align: 'left'
		},
		assistant: {
			bg: 'var(--color-primary)',
			text: 'white',
			align: 'right'
		},
		tool: {
			bg: 'var(--color-surface)',
			text: 'var(--color-text-muted)',
			align: 'left'
		}
	};

	$effect(() => {
		if (agent_id) {
			fetchMessages(agent_id);
		} else {
			messages = [];
		}
	});

	async function fetchMessages(aid: string) {
		loading = true;
		error = '';
		try {
			const res = await fetch(`/api/agents/${aid}/messages`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			messages = await res.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load messages';
			messages = [];
		} finally {
			loading = false;
		}
	}
</script>

{#if agent_id}
	<div
		class="fixed top-12 right-0 bottom-0 overflow-y-auto z-40 border-l"
		style="width: 400px; background: var(--color-surface); border-color: var(--color-border);"
	>
		<div class="p-4">
			<div class="flex items-center justify-between mb-4">
				<h3 class="text-sm font-semibold">Conversation</h3>
				<button
					onclick={onclose}
					class="text-sm cursor-pointer border-none"
					style="background: transparent; color: var(--color-text-muted);"
				>&times;</button>
			</div>

			{#if loading}
				<div class="text-xs" style="color: var(--color-text-muted);">Loading messages...</div>
			{:else if error}
				<div class="text-xs" style="color: var(--color-error);">{error}</div>
			{:else if messages.length === 0}
				<div class="text-xs" style="color: var(--color-text-muted);">No messages captured for this agent.</div>
			{:else}
				<div class="space-y-3">
					{#each messages as msg}
						{@const style = roleStyles[msg.role] ?? roleStyles.tool}
						<div
							class="text-xs"
							style="text-align: {style.align};"
						>
							<div class="flex items-center gap-1 mb-1" style="justify-content: {style.align === 'right' ? 'flex-end' : 'flex-start'};">
								<span
									class="inline-block px-1.5 py-0.5 rounded text-xs font-medium"
									style="background: {style.bg}; color: {style.text};"
								>{msg.role}</span>
								{#if msg.synthetic}
									<span
										class="inline-block px-1.5 py-0.5 rounded text-xs"
										style="background: var(--color-surface-2); color: var(--color-text-muted); border: 1px dashed var(--color-border);"
									>inferred</span>
								{/if}
								<span style="color: var(--color-text-muted); font-size: 10px;">
									{new Date(msg.timestamp).toLocaleTimeString()}
								</span>
							</div>
							<div
								class="p-2 rounded text-xs overflow-y-auto"
								style="
									background: var(--color-bg);
									max-height: 200px;
									white-space: pre-wrap;
									word-break: break-word;
									{msg.synthetic ? 'border: 1px dashed var(--color-border); opacity: 0.8;' : 'border: 1px solid var(--color-border);'}
								"
							>{msg.content ?? msg.content_preview ?? ''}</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}
