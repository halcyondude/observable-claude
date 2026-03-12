<script lang="ts">
	import StatCard from '$lib/components/StatCard.svelte';
	import { events, agentCount } from '$lib/stores/events';
	import { activeSessionId } from '$lib/stores/session';
	import type { ObserverEvent, ToolStats } from '$lib/types/events';

	let timeRange = $state<'5m' | '30m' | '1h' | 'session' | 'all'>('session');

	function getTimeRangeMs(range: typeof timeRange): number {
		switch (range) {
			case '5m': return 5 * 60 * 1000;
			case '30m': return 30 * 60 * 1000;
			case '1h': return 60 * 60 * 1000;
			default: return Infinity;
		}
	}

	let filteredEvents = $derived.by(() => {
		let result = $events;
		const sid = $activeSessionId;

		if (timeRange === 'session' && sid) {
			result = result.filter((e) => e.session_id === sid);
		} else if (timeRange !== 'all') {
			const cutoff = Date.now() - getTimeRangeMs(timeRange);
			result = result.filter((e) => new Date(e.received_at).getTime() >= cutoff);
		}

		return result;
	});

	let totalEvents = $derived(filteredEvents.length);

	let toolSuccessRate = $derived.by(() => {
		const posts = filteredEvents.filter(
			(e) => e.event_type === 'PostToolUse' || e.event_type === 'PostToolUseFailure'
		);
		if (posts.length === 0) return 100;
		const success = posts.filter((e) => e.event_type === 'PostToolUse').length;
		return Math.round((success / posts.length) * 100);
	});

	let toolStats = $derived.by(() => {
		const map = new Map<string, { durations: number[]; success: number; fail: number }>();

		for (const e of filteredEvents) {
			if (e.event_type !== 'PostToolUse' && e.event_type !== 'PostToolUseFailure') continue;
			const name = e.tool_name ?? 'unknown';
			if (!map.has(name)) map.set(name, { durations: [], success: 0, fail: 0 });
			const stat = map.get(name)!;
			if (e.event_type === 'PostToolUse') stat.success++;
			else stat.fail++;
			const dur = (e.payload as any)?.duration_ms;
			if (typeof dur === 'number') stat.durations.push(dur);
		}

		const result: ToolStats[] = [];
		for (const [name, stat] of map) {
			const sorted = stat.durations.sort((a, b) => a - b);
			const p50 = sorted.length > 0 ? sorted[Math.floor(sorted.length * 0.5)] : 0;
			const p95 = sorted.length > 0 ? sorted[Math.floor(sorted.length * 0.95)] : 0;
			result.push({
				tool_name: name,
				call_count: stat.success + stat.fail,
				success_count: stat.success,
				fail_count: stat.fail,
				p50_ms: Math.round(p50),
				p95_ms: Math.round(p95)
			});
		}

		return result.sort((a, b) => b.p95_ms - a.p95_ms);
	});

	let medianLatency = $derived.by(() => {
		const allDurations: number[] = [];
		for (const e of filteredEvents) {
			const dur = (e.payload as any)?.duration_ms;
			if (typeof dur === 'number') allDurations.push(dur);
		}
		if (allDurations.length === 0) return { p50: 0, p95: 0 };
		allDurations.sort((a, b) => a - b);
		return {
			p50: Math.round(allDurations[Math.floor(allDurations.length * 0.5)]),
			p95: Math.round(allDurations[Math.floor(allDurations.length * 0.95)])
		};
	});

	let eventBuckets = $derived.by(() => {
		const bucketSize = 10_000; // 10s
		const buckets = new Map<number, Map<string, number>>();

		for (const e of filteredEvents) {
			const ts = new Date(e.received_at).getTime();
			const bucket = Math.floor(ts / bucketSize) * bucketSize;
			if (!buckets.has(bucket)) buckets.set(bucket, new Map());
			const typeMap = buckets.get(bucket)!;
			typeMap.set(e.event_type, (typeMap.get(e.event_type) ?? 0) + 1);
		}

		return Array.from(buckets.entries())
			.sort((a, b) => a[0] - b[0])
			.map(([ts, types]) => ({
				timestamp: ts,
				total: Array.from(types.values()).reduce((a, b) => a + b, 0),
				types: Object.fromEntries(types)
			}));
	});

	function latencyColor(ms: number): string {
		if (ms < 100) return 'var(--color-primary)';
		if (ms <= 500) return 'var(--color-warning)';
		return 'var(--color-error)';
	}

	function successRateColor(rate: number): string {
		if (rate >= 95) return 'var(--color-success)';
		if (rate >= 80) return 'var(--color-warning)';
		return 'var(--color-error)';
	}

	let maxP95 = $derived(Math.max(1, ...toolStats.map((t) => t.p95_ms)));
	let maxBucket = $derived(Math.max(1, ...eventBuckets.map((b) => b.total)));

	let sortColumn = $state<'name' | 'calls' | 'p50' | 'p95'>('p95');
	let sortAsc = $state(false);

	let sortedStats = $derived.by(() => {
		const copy = [...toolStats];
		copy.sort((a, b) => {
			let cmp = 0;
			switch (sortColumn) {
				case 'name': cmp = a.tool_name.localeCompare(b.tool_name); break;
				case 'calls': cmp = a.call_count - b.call_count; break;
				case 'p50': cmp = a.p50_ms - b.p50_ms; break;
				case 'p95': cmp = a.p95_ms - b.p95_ms; break;
			}
			return sortAsc ? cmp : -cmp;
		});
		return copy;
	});

	function toggleSort(col: typeof sortColumn) {
		if (sortColumn === col) {
			sortAsc = !sortAsc;
		} else {
			sortColumn = col;
			sortAsc = false;
		}
	}
</script>

<div class="p-6 space-y-6 overflow-y-auto h-full" style="background: var(--color-bg);">
	<!-- Time range selector -->
	<div class="flex items-center gap-2">
		{#each (['5m', '30m', '1h', 'session', 'all'] as const) as range}
			<button
				onclick={() => timeRange = range}
				class="px-3 py-1 rounded text-xs cursor-pointer border-none"
				style="background: {timeRange === range ? 'var(--color-primary)' : 'var(--color-surface)'}; color: {timeRange === range ? 'white' : 'var(--color-text-muted)'};"
			>
				{range === 'session' ? 'Session' : range === 'all' ? 'All time' : `Last ${range}`}
			</button>
		{/each}
	</div>

	<!-- Stat cards -->
	<div class="grid gap-4" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
		<StatCard label="Total Events" value={String(totalEvents)} />
		<StatCard
			label="Active Agents"
			value={String($agentCount.active)}
			subtitle="of {$agentCount.total} total"
		/>
		<StatCard
			label="Tool Success Rate"
			value="{toolSuccessRate}%"
			deltaColor={successRateColor(toolSuccessRate)}
		/>
		<StatCard
			label="Median Latency"
			value="{medianLatency.p50}ms"
			subtitle="p95: {medianLatency.p95}ms"
		/>
	</div>

	<!-- Tool Latency Chart -->
	{#if toolStats.length > 0}
		<div class="rounded-lg p-4" style="background: var(--color-surface); border: 1px solid var(--color-border);">
			<h3 class="text-sm font-semibold mb-3">Tool Latency</h3>
			<div class="space-y-2">
				{#each toolStats.slice(0, 15) as tool}
					<div class="flex items-center gap-3 text-xs">
						<span class="font-mono shrink-0" style="width: 160px; color: var(--color-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
							{tool.tool_name}
						</span>
						<div class="flex-1 h-4 rounded overflow-hidden" style="background: var(--color-bg);">
							<div
								class="h-full rounded"
								style="width: {(tool.p50_ms / maxP95) * 100}%; background: {latencyColor(tool.p50_ms)}; position: relative;"
							>
								{#if tool.p95_ms > tool.p50_ms}
									<div
										class="absolute top-0 h-full rounded-r"
										style="left: 100%; width: {((tool.p95_ms - tool.p50_ms) / maxP95) * 100}%; background: {latencyColor(tool.p95_ms)}; opacity: 0.4;"
									></div>
								{/if}
							</div>
						</div>
						<span class="font-mono shrink-0" style="width: 100px; color: var(--color-text-muted); text-align: right;">
							{tool.p50_ms} / {tool.p95_ms}ms
						</span>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Event Rate Chart -->
	{#if eventBuckets.length > 1}
		<div class="rounded-lg p-4" style="background: var(--color-surface); border: 1px solid var(--color-border);">
			<h3 class="text-sm font-semibold mb-3">Event Rate (per 10s)</h3>
			<div class="flex items-end gap-px" style="height: 120px;">
				{#each eventBuckets as bucket}
					<div
						class="flex-1 rounded-t"
						style="height: {(bucket.total / maxBucket) * 100}%; background: var(--color-primary); min-width: 2px; opacity: 0.8;"
						title="{new Date(bucket.timestamp).toLocaleTimeString()}: {bucket.total} events"
					></div>
				{/each}
			</div>
			<div class="flex justify-between mt-1 text-xs" style="color: var(--color-text-muted);">
				{#if eventBuckets.length > 0}
					<span>{new Date(eventBuckets[0].timestamp).toLocaleTimeString()}</span>
					<span>{new Date(eventBuckets[eventBuckets.length - 1].timestamp).toLocaleTimeString()}</span>
				{/if}
			</div>
		</div>
	{/if}

	<!-- Per-tool table -->
	{#if sortedStats.length > 0}
		<div class="rounded-lg overflow-hidden" style="background: var(--color-surface); border: 1px solid var(--color-border);">
			<table class="w-full text-xs">
				<thead>
					<tr style="border-bottom: 1px solid var(--color-border);">
						<th
							class="text-left px-4 py-2 cursor-pointer font-medium"
							style="color: var(--color-text-muted);"
							onclick={() => toggleSort('name')}
						>Tool</th>
						<th
							class="text-right px-4 py-2 cursor-pointer font-medium"
							style="color: var(--color-text-muted);"
							onclick={() => toggleSort('calls')}
						>Calls</th>
						<th
							class="text-right px-4 py-2 cursor-pointer font-medium"
							style="color: var(--color-text-muted);"
							onclick={() => toggleSort('p50')}
						>p50</th>
						<th
							class="text-right px-4 py-2 cursor-pointer font-medium"
							style="color: var(--color-text-muted);"
							onclick={() => toggleSort('p95')}
						>p95</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedStats as tool}
						<tr style="border-bottom: 1px solid var(--color-border);">
							<td class="px-4 py-2 font-mono">{tool.tool_name}</td>
							<td class="px-4 py-2 text-right">
								<span style="color: var(--color-success);">{tool.success_count}</span>
								{#if tool.fail_count > 0}
									<span style="color: var(--color-text-muted);"> / </span>
									<span style="color: var(--color-error);">{tool.fail_count}</span>
								{/if}
							</td>
							<td class="px-4 py-2 text-right font-mono" style="color: {latencyColor(tool.p50_ms)};">
								{tool.p50_ms}ms
							</td>
							<td class="px-4 py-2 text-right font-mono" style="color: {latencyColor(tool.p95_ms)};">
								{tool.p95_ms}ms
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
