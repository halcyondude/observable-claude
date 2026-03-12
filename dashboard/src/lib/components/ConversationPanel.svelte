<script lang="ts">
	import type { MessageSearchResult } from '$lib/types/events';

	interface Props {
		messages: MessageSearchResult[];
		agentId?: string;
	}

	let { messages, agentId }: Props = $props();

	let filterText = $state('');

	let filteredMessages = $derived.by(() => {
		if (!filterText.trim()) return messages.map((m) => ({ ...m, _dimmed: false }));
		const q = filterText.toLowerCase();
		return messages.map((m) => ({
			...m,
			_dimmed: !m.content_preview.toLowerCase().includes(q)
		}));
	});

	function highlightMatch(text: string, query: string): string {
		if (!query.trim()) return escapeHtml(text);
		const escaped = escapeHtml(text);
		const q = escapeHtml(query);
		const regex = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
		return escaped.replace(
			regex,
			'<mark style="background: var(--color-primary); color: white; padding: 0 2px; border-radius: 2px;">$1</mark>'
		);
	}

	function escapeHtml(str: string): string {
		return str
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	}

	function roleBadgeColor(role: string): string {
		switch (role) {
			case 'user':
				return 'var(--color-primary)';
			case 'assistant':
				return 'var(--color-success, #22c55e)';
			case 'system':
				return 'var(--color-warning, #eab308)';
			default:
				return 'var(--color-text-muted)';
		}
	}

	function formatTimestamp(ts: string): string {
		try {
			const d = new Date(ts);
			return d.toLocaleTimeString(undefined, {
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit'
			});
		} catch {
			return ts;
		}
	}
</script>

<div class="flex flex-col h-full">
	<!-- Filter input -->
	<div class="p-2" style="border-bottom: 1px solid var(--color-border);">
		<input
			bind:value={filterText}
			placeholder="Filter messages..."
			class="w-full px-2 py-1.5 rounded text-xs border-none outline-none"
			style="background: var(--color-surface-2); color: var(--color-text);"
		/>
	</div>

	{#if agentId}
		<div class="px-3 py-1.5 text-[10px] font-mono" style="color: var(--color-text-muted); border-bottom: 1px solid var(--color-border);">
			Agent: {agentId}
		</div>
	{/if}

	<!-- Messages list -->
	<div class="flex-1 overflow-y-auto p-2 space-y-2">
		{#if filteredMessages.length === 0}
			<div class="text-xs p-4 text-center" style="color: var(--color-text-muted);">
				No messages{filterText ? ' match your filter' : ' available'}
			</div>
		{:else}
			{#each filteredMessages as msg}
				<div
					class="p-2.5 rounded-lg text-xs transition-opacity"
					style="
						background: var(--color-surface);
						border: 1px solid var(--color-border);
						opacity: {msg._dimmed ? '0.3' : '1'};
						{msg.role === 'assistant' ? 'margin-left: 16px;' : msg.role === 'system' ? 'margin-right: 16px; border-left: 2px solid ' + roleBadgeColor('system') + ';' : ''}
					"
				>
					<div class="flex items-center gap-1.5 mb-1">
						<span
							class="px-1.5 py-0.5 rounded text-[10px] font-medium"
							style="background: {roleBadgeColor(msg.role)}20; color: {roleBadgeColor(msg.role)};"
						>{msg.role}</span>
						<span class="text-[10px] font-mono" style="color: var(--color-text-muted);">#{msg.sequence}</span>
						<span class="flex-1"></span>
						<span class="text-[10px]" style="color: var(--color-text-muted);">{formatTimestamp(msg.timestamp)}</span>
					</div>
					<div class="font-mono whitespace-pre-wrap leading-relaxed" style="color: var(--color-text); font-size: 11px;">
						{#if filterText.trim()}
							{@html highlightMatch(msg.content_preview, filterText)}
						{:else}
							{msg.content_preview}
						{/if}
					</div>
				</div>
			{/each}
		{/if}
	</div>
</div>
