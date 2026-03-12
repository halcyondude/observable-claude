<script lang="ts">
	import { onMount } from 'svelte';
	import { askQuestion, executeCypher } from '$lib/services/api';
	import type { QueryResult } from '$lib/types/events';

	let mode = $state<'nl' | 'cypher'>('nl');
	let input = $state('');
	let loading = $state(false);
	let result = $state<QueryResult | null>(null);
	let error = $state<string | null>(null);
	let showCypher = $state(false);
	let queryHistory = $state<string[]>([]);
	let showHistory = $state(false);
	let inputEl: HTMLTextAreaElement;

	const exampleChips = [
		'Which agents are currently running?',
		'Show me the spawn tree for this session',
		'What tool calls failed in the last 10 minutes?',
		'Which skills were loaded most often today?',
		'What was the slowest tool call this session?'
	];

	let sortColumn = $state<number | null>(null);
	let sortAsc = $state(true);

	let sortedRows = $derived.by(() => {
		if (!result?.rows || sortColumn === null) return result?.rows ?? [];
		const col = result.columns[sortColumn];
		const copy = [...result.rows];
		copy.sort((a, b) => {
			const va = a[col];
			const vb = b[col];
			if (va == null && vb == null) return 0;
			if (va == null) return 1;
			if (vb == null) return -1;
			if (typeof va === 'number' && typeof vb === 'number') {
				return sortAsc ? va - vb : vb - va;
			}
			return sortAsc
				? String(va).localeCompare(String(vb))
				: String(vb).localeCompare(String(va));
		});
		return copy;
	});

	function toggleSort(idx: number) {
		if (sortColumn === idx) {
			sortAsc = !sortAsc;
		} else {
			sortColumn = idx;
			sortAsc = true;
		}
	}

	async function submit() {
		if (!input.trim() || loading) return;

		loading = true;
		error = null;
		result = null;

		try {
			if (mode === 'nl') {
				result = await askQuestion(input.trim());
			} else {
				result = await executeCypher(input.trim());
			}

			// Save to history
			const trimmed = input.trim();
			queryHistory = [trimmed, ...queryHistory.filter((q) => q !== trimmed)].slice(0, 20);
			if (typeof localStorage !== 'undefined') {
				localStorage.setItem('cc-observer-query-history', JSON.stringify(queryHistory));
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Query failed';
		} finally {
			loading = false;
		}
	}

	function useChip(text: string) {
		input = text;
		submit();
	}

	function loadFromHistory(q: string) {
		input = q;
		showHistory = false;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && e.metaKey) {
			e.preventDefault();
			submit();
		}
	}

	onMount(() => {
		if (typeof localStorage !== 'undefined') {
			try {
				const stored = localStorage.getItem('cc-observer-query-history');
				if (stored) queryHistory = JSON.parse(stored);
			} catch {}
		}

		function handleGlobalKey(e: KeyboardEvent) {
			if (e.key === '/' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) {
				e.preventDefault();
				inputEl?.focus();
			}
		}
		window.addEventListener('keydown', handleGlobalKey);
		return () => window.removeEventListener('keydown', handleGlobalKey);
	});
</script>

<div class="flex flex-col h-full p-6 space-y-4 overflow-y-auto" style="background: var(--color-bg);">
	<!-- Mode toggle -->
	<div class="flex items-center gap-2">
		<button
			onclick={() => mode = 'nl'}
			class="px-3 py-1.5 rounded text-xs cursor-pointer border-none"
			style="background: {mode === 'nl' ? 'var(--color-primary)' : 'var(--color-surface)'}; color: {mode === 'nl' ? 'white' : 'var(--color-text-muted)'};"
		>Natural Language</button>
		<button
			onclick={() => mode = 'cypher'}
			class="px-3 py-1.5 rounded text-xs cursor-pointer border-none"
			style="background: {mode === 'cypher' ? 'var(--color-primary)' : 'var(--color-surface)'}; color: {mode === 'cypher' ? 'white' : 'var(--color-text-muted)'};"
		>Cypher</button>

		<div class="flex-1"></div>

		{#if queryHistory.length > 0}
			<div class="relative">
				<button
					onclick={() => showHistory = !showHistory}
					class="px-2 py-1 rounded text-xs cursor-pointer border-none"
					style="background: var(--color-surface); color: var(--color-text-muted);"
				>History ({queryHistory.length})</button>
				{#if showHistory}
					<div
						class="absolute right-0 top-full mt-1 w-80 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto"
						style="background: var(--color-surface); border: 1px solid var(--color-border);"
					>
						{#each queryHistory as q}
							<button
								onclick={() => loadFromHistory(q)}
								class="w-full text-left px-3 py-2 text-xs cursor-pointer border-none truncate"
								style="background: transparent; color: var(--color-text);"
							>{q}</button>
						{/each}
					</div>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Input -->
	<div class="flex gap-2">
		<textarea
			bind:this={inputEl}
			bind:value={input}
			onkeydown={handleKeydown}
			placeholder={mode === 'nl'
				? 'Which agents are currently running?'
				: 'MATCH (a:Agent) RETURN a.agent_type, a.status'}
			class="flex-1 px-3 py-2 rounded-lg text-sm resize-y border-none outline-none"
			style="background: var(--color-surface-2); color: var(--color-text); min-height: 60px; max-height: 200px; font-family: {mode === 'cypher' ? "'JetBrains Mono', monospace" : 'inherit'};"
			rows="3"
		></textarea>
		<button
			onclick={submit}
			disabled={loading || !input.trim()}
			class="px-4 py-2 rounded-lg text-sm font-medium cursor-pointer border-none self-end"
			style="background: var(--color-primary); color: white; opacity: {loading || !input.trim() ? '0.5' : '1'};"
		>
			{#if loading}
				...
			{:else}
				Ask
			{/if}
		</button>
	</div>

	<!-- Example chips (NL mode only) -->
	{#if mode === 'nl' && !result && !error}
		<div class="flex flex-wrap gap-2">
			{#each exampleChips as chip}
				<button
					onclick={() => useChip(chip)}
					class="px-3 py-1.5 rounded-full text-xs cursor-pointer border-none"
					style="background: var(--color-surface); color: var(--color-text-muted); border: 1px solid var(--color-border);"
				>{chip}</button>
			{/each}
		</div>
	{/if}

	<!-- Error -->
	{#if error}
		<div
			class="p-3 rounded-lg text-sm"
			style="background: rgba(202, 103, 2, 0.1); border: 1px solid var(--color-error); color: var(--color-error);"
		>
			{error}
			<button
				onclick={submit}
				class="ml-2 underline cursor-pointer border-none text-xs"
				style="background: transparent; color: var(--color-error);"
			>Retry</button>
		</div>
	{/if}

	<!-- Generated Cypher (NL mode) -->
	{#if result?.cypher && mode === 'nl'}
		<div>
			<button
				onclick={() => showCypher = !showCypher}
				class="text-xs cursor-pointer border-none"
				style="background: transparent; color: var(--color-text-muted);"
			>
				{showCypher ? 'Hide' : 'Show'} generated Cypher
			</button>
			{#if showCypher}
				<pre
					class="mt-1 p-3 rounded-lg text-xs font-mono overflow-x-auto"
					style="background: var(--color-surface-2); color: var(--color-primary);"
				>{result.cypher}</pre>
			{/if}
		</div>
	{/if}

	<!-- Explanation -->
	{#if result?.explanation}
		<p class="text-xs" style="color: var(--color-text-muted);">{result.explanation}</p>
	{/if}

	<!-- Results table -->
	{#if result && result.columns.length > 0}
		<div class="rounded-lg overflow-auto" style="background: var(--color-surface); border: 1px solid var(--color-border);">
			<table class="w-full text-xs">
				<thead>
					<tr style="border-bottom: 1px solid var(--color-border);">
						{#each result.columns as col, idx}
							<th
								class="text-left px-3 py-2 cursor-pointer font-medium"
								style="color: var(--color-text-muted);"
								onclick={() => toggleSort(idx)}
							>{col}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each sortedRows as row}
						<tr style="border-bottom: 1px solid var(--color-border);">
							{#each result.columns as col}
								<td class="px-3 py-2 font-mono">{row[col] ?? ''}</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{:else if result && result.columns.length === 0}
		<div class="text-sm" style="color: var(--color-text-muted);">No results</div>
	{/if}
</div>
