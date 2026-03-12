<script lang="ts">
	import { onMount } from 'svelte';
	import { getAgentMessages } from '$lib/services/api';
	import type { AgentMessage } from '$lib/types/events';

	let { agentId }: { agentId: string } = $props();

	let messages = $state<AgentMessage[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let expandedMessages = $state<Set<string>>(new Set());
	let scrollContainer = $state<HTMLDivElement>(undefined!);
	let copyFeedback = $state<string | null>(null);

	const PREVIEW_LENGTH = 500;

	async function loadMessages(id: string) {
		loading = true;
		error = null;
		try {
			messages = await getAgentMessages(id);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load messages';
			messages = [];
		} finally {
			loading = false;
		}
	}

	function toggleExpand(messageId: string) {
		const next = new Set(expandedMessages);
		if (next.has(messageId)) {
			next.delete(messageId);
		} else {
			next.add(messageId);
		}
		expandedMessages = next;
	}

	function isLong(content: string): boolean {
		return content.length > PREVIEW_LENGTH;
	}

	function previewContent(content: string): string {
		return content.slice(0, PREVIEW_LENGTH);
	}

	function formatTimestamp(ts: string): string {
		return new Date(ts).toLocaleTimeString([], {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});
	}

	async function copyText(text: string, label: string) {
		try {
			await navigator.clipboard.writeText(text);
			copyFeedback = label;
			setTimeout(() => { copyFeedback = null; }, 1500);
		} catch {
			// clipboard API may not be available
		}
	}

	function copyMessage(msg: AgentMessage) {
		copyText(msg.content, msg.message_id);
	}

	function copyAll() {
		const text = messages
			.map((m) => `[${m.role}] ${m.content}`)
			.join('\n\n---\n\n');
		copyText(text, '__all__');
	}

	$effect(() => {
		if (agentId) {
			loadMessages(agentId);
		}
	});

	$effect(() => {
		if (!loading && messages.length > 0 && scrollContainer) {
			// Scroll to bottom after messages render
			requestAnimationFrame(() => {
				scrollContainer.scrollTop = scrollContainer.scrollHeight;
			});
		}
	});
</script>

<div class="flex flex-col h-full">
	{#if loading}
		<div class="flex-1 flex items-center justify-center">
			<span class="text-xs" style="color: var(--color-text-muted);">Loading messages...</span>
		</div>
	{:else if error}
		<div class="flex-1 flex items-center justify-center">
			<span class="text-xs" style="color: var(--color-error);">{error}</span>
		</div>
	{:else if messages.length === 0}
		<div class="flex-1 flex items-center justify-center">
			<span class="text-xs" style="color: var(--color-text-muted);">No messages captured</span>
		</div>
	{:else}
		<!-- Copy All header -->
		<div class="flex items-center justify-end px-3 py-2 border-b" style="border-color: var(--color-border);">
			<button
				onclick={copyAll}
				class="text-xs cursor-pointer border-none px-2 py-1 rounded"
				style="background: var(--color-surface-2); color: var(--color-text-muted);"
			>
				{copyFeedback === '__all__' ? 'Copied' : 'Copy All'}
			</button>
		</div>

		<!-- Messages -->
		<div
			bind:this={scrollContainer}
			class="flex-1 overflow-y-auto px-3 py-3 space-y-3"
		>
			{#each messages as msg (msg.message_id)}
				{@const isAssistant = msg.role === 'assistant'}
				{@const expanded = expandedMessages.has(msg.message_id)}
				{@const long = isLong(msg.content)}

				<div class="flex {isAssistant ? 'justify-end' : 'justify-start'}">
					<div
						class="max-w-[85%] rounded-lg px-3 py-2"
						style="background: {isAssistant
							? 'rgba(10, 147, 150, 0.1)'
							: 'var(--color-surface)'};"
					>
						<!-- Header: role badge + timestamp -->
						<div class="flex items-center gap-2 mb-1">
							<span
								class="inline-block px-1.5 py-0.5 rounded text-xs font-medium"
								style="background: var(--color-surface-2); color: var(--color-text-muted); font-size: 10px;"
							>{msg.role}</span>
							<span class="text-xs" style="color: var(--color-text-muted); font-size: 10px;">
								{formatTimestamp(msg.timestamp)}
							</span>
						</div>

						<!-- Content -->
						<div
							class="text-xs mt-1"
							style="white-space: pre-wrap; word-break: break-word; color: var(--color-text);"
						>{#if long && !expanded}{previewContent(msg.content)}{:else}{msg.content}{/if}</div>

						<!-- Controls -->
						<div class="flex items-center gap-2 mt-2">
							{#if long}
								<button
									onclick={() => toggleExpand(msg.message_id)}
									class="text-xs cursor-pointer border-none px-0 py-0"
									style="background: transparent; color: var(--color-primary); font-size: 10px;"
								>
									{expanded ? 'Show less' : 'Show more'}
								</button>
							{/if}
							<button
								onclick={() => copyMessage(msg)}
								class="text-xs cursor-pointer border-none px-0 py-0"
								style="background: transparent; color: var(--color-text-muted); font-size: 10px;"
							>
								{copyFeedback === msg.message_id ? 'Copied' : 'Copy'}
							</button>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
