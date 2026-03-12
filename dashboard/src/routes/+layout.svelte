<script lang="ts">
	import '../app.css';
	import TopBar from '$lib/components/TopBar.svelte';
	import Sidebar from '$lib/components/Sidebar.svelte';
	import { viewingArchived, returnToLive, activeSession } from '$lib/stores/session';
	import { connectSSE, disconnectSSE } from '$lib/services/sse';
	import { getAgentFromUrl, navigateToToolFeed } from '$lib/services/navigation';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	let { children } = $props();

	onMount(() => {
		connectSSE();

		const viewRoutes = ['/tree', '/timeline', '/tools', '/analytics', '/query', '/sessions'];

		function handleKeydown(e: KeyboardEvent) {
			if (e.metaKey && e.key >= '1' && e.key <= '6') {
				e.preventDefault();
				const idx = parseInt(e.key) - 1;
				goto(viewRoutes[idx]);
			}
			if (e.key === 'Escape') {
				document.dispatchEvent(new CustomEvent('close-panels'));
			}
			if (e.key === 'f' || e.key === 'F') {
				const tag = (e.target as HTMLElement)?.tagName;
				if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
					e.preventDefault();
					const agentId = getAgentFromUrl();
					navigateToToolFeed(agentId ?? undefined);
				}
			}
		}

		window.addEventListener('keydown', handleKeydown);
		return () => {
			disconnectSSE();
			window.removeEventListener('keydown', handleKeydown);
		};
	});
</script>

<div class="flex flex-col h-screen overflow-hidden">
	<TopBar />

	{#if $viewingArchived && $activeSession}
		<div
			class="flex items-center justify-between px-4 py-2 text-xs"
			style="background: var(--color-surface-2); color: var(--color-text-muted); border-bottom: 1px solid var(--color-border);"
		>
			<span>
				Viewing archived session &mdash;
				<span class="font-mono">{$activeSession.session_id}</span>
			</span>
			<button
				onclick={() => returnToLive()}
				class="px-3 py-1 rounded text-xs cursor-pointer border-none"
				style="background: var(--color-primary); color: white;"
			>
				Return to live
			</button>
		</div>
	{/if}

	<div class="flex flex-1 overflow-hidden">
		<Sidebar />
		<main class="flex-1 overflow-auto">
			{@render children()}
		</main>
	</div>
</div>
