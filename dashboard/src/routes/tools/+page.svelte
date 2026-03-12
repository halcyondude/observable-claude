<script lang="ts">
	import { onMount } from 'svelte';
	import EventRow from '$lib/components/EventRow.svelte';
	import { toolEvents, toolNames, unreadToolCount } from '$lib/stores/events';
	import type { ObserverEvent } from '$lib/types/events';

	let paused = $state(false);
	let filterTypes = $state<Set<string>>(new Set());
	let filterTool = $state('');
	let filterStatus = $state<'all' | 'success' | 'failure'>('all');
	let scrollContainer: HTMLDivElement;
	let wasScrolledUp = false;

	const typeOptions = ['PreToolUse', 'PostToolUse', 'PostToolUseFailure'] as const;

	function toggleType(type: string) {
		filterTypes = new Set(filterTypes);
		if (filterTypes.has(type)) {
			filterTypes.delete(type);
		} else {
			filterTypes.add(type);
		}
	}

	let filteredEvents = $derived.by(() => {
		let result = $toolEvents;

		if (filterTypes.size > 0) {
			result = result.filter((e) => filterTypes.has(e.event_type));
		}

		if (filterTool) {
			const lower = filterTool.toLowerCase();
			result = result.filter((e) => e.tool_name?.toLowerCase().includes(lower));
		}

		if (filterStatus === 'success') {
			result = result.filter((e) => e.event_type !== 'PostToolUseFailure');
		} else if (filterStatus === 'failure') {
			result = result.filter((e) => e.event_type === 'PostToolUseFailure');
		}

		return result;
	});

	function handleScroll() {
		if (!scrollContainer) return;
		const { scrollTop } = scrollContainer;
		if (scrollTop > 50 && !paused) {
			paused = true;
			wasScrolledUp = true;
		}
	}

	function togglePause() {
		paused = !paused;
		if (!paused && scrollContainer) {
			scrollContainer.scrollTop = 0;
			wasScrolledUp = false;
		}
	}

	onMount(() => {
		unreadToolCount.set(0);

		function handleKeydown(e: KeyboardEvent) {
			if (e.key === ' ' && !e.metaKey && !e.ctrlKey) {
				const tag = (e.target as HTMLElement)?.tagName;
				if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
					e.preventDefault();
					togglePause();
				}
			}
		}
		window.addEventListener('keydown', handleKeydown);
		return () => window.removeEventListener('keydown', handleKeydown);
	});
</script>

<div class="flex flex-col h-full">
	<!-- Filter bar -->
	<div
		class="flex items-center gap-3 px-4 py-2 border-b flex-wrap"
		style="background: var(--color-surface); border-color: var(--color-border);"
	>
		<div class="flex gap-1">
			{#each typeOptions as type}
				{@const active = filterTypes.has(type)}
				<button
					onclick={() => toggleType(type)}
					class="px-2 py-1 rounded text-xs cursor-pointer border-none"
					style="background: {active ? 'var(--color-primary)' : 'var(--color-surface-2)'}; color: {active ? 'white' : 'var(--color-text-muted)'};"
				>
					{type === 'PreToolUse' ? 'PRE' : type === 'PostToolUse' ? 'POST' : 'FAIL'}
				</button>
			{/each}
		</div>

		<input
			type="text"
			placeholder="Filter tool name..."
			bind:value={filterTool}
			class="px-2 py-1 rounded text-xs border-none outline-none"
			style="background: var(--color-surface-2); color: var(--color-text); width: 160px;"
			list="tool-names"
		/>
		<datalist id="tool-names">
			{#each $toolNames as name}
				<option value={name}></option>
			{/each}
		</datalist>

		<select
			bind:value={filterStatus}
			class="px-2 py-1 rounded text-xs border-none outline-none cursor-pointer"
			style="background: var(--color-surface-2); color: var(--color-text);"
		>
			<option value="all">All</option>
			<option value="success">Success</option>
			<option value="failure">Failure</option>
		</select>

		<div class="flex-1"></div>

		<button
			onclick={togglePause}
			class="px-3 py-1 rounded text-xs font-medium cursor-pointer border-none"
			style="background: {paused ? 'var(--color-warning)' : 'var(--color-surface-2)'}; color: {paused ? '#0D1B2A' : 'var(--color-text-muted)'};"
		>
			{paused ? 'Resume' : 'Pause'}
		</button>

		<span class="text-xs" style="color: var(--color-text-muted);">
			{filteredEvents.length} events
		</span>
	</div>

	<!-- Event list -->
	<div
		bind:this={scrollContainer}
		onscroll={handleScroll}
		class="flex-1 overflow-y-auto"
		style="background: var(--color-bg);"
	>
		{#if filteredEvents.length === 0}
			<div class="flex items-center justify-center h-full" style="color: var(--color-text-muted);">
				<span class="text-sm">No tool events yet</span>
			</div>
		{:else}
			<div class="space-y-px">
				{#each filteredEvents as event (event.event_id)}
					<EventRow {event} />
				{/each}
			</div>
		{/if}
	</div>
</div>
