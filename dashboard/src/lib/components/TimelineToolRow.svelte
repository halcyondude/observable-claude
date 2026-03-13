<script lang="ts">
	import { getToolColor } from '$lib/stores/tool-families';
	import { goto } from '$app/navigation';

	interface ToolCall {
		name: string;
		status: string;
		start_ts: number;
		end_ts: number;
		duration_ms: number;
	}

	interface Props {
		toolCalls: ToolCall[];
		timeScale: (timestamp: number) => number;
		agentStart: number;
		agentEnd: number;
		p95Map: Map<string, number>;
	}

	let { toolCalls, timeScale, agentStart, agentEnd, p95Map }: Props = $props();

	const BAR_HEIGHT = 16;
	const BAR_GAP = 2;
	const MIN_BAR_WIDTH = 4;
	const LABEL_MIN_WIDTH = 60;

	function isOutlier(tc: ToolCall): boolean {
		const threshold = p95Map.get(tc.name);
		if (threshold == null) return false;
		return tc.duration_ms > threshold;
	}

	function barColor(tc: ToolCall): string {
		if (tc.status === 'failed') return '#CA6702';
		return getToolColor(tc.name);
	}

	function handleBarClick(tc: ToolCall) {
		goto(`/tools?tool_name=${encodeURIComponent(tc.name)}`);
	}

	// Layout: stack concurrent tool calls into swim lanes
	function layoutBars(calls: ToolCall[]): Array<ToolCall & { lane: number }> {
		const sorted = [...calls].sort((a, b) => a.start_ts - b.start_ts);
		const lanes: number[] = []; // end time of each lane
		return sorted.map((tc) => {
			let lane = 0;
			for (let i = 0; i < lanes.length; i++) {
				if (tc.start_ts >= lanes[i]) {
					lane = i;
					break;
				}
				lane = i + 1;
			}
			lanes[lane] = tc.end_ts;
			return { ...tc, lane };
		});
	}

	let laidOut = $derived(layoutBars(toolCalls));
	let maxLane = $derived(laidOut.length > 0 ? Math.max(...laidOut.map((t) => t.lane)) : 0);
	let totalHeight = $derived((maxLane + 1) * (BAR_HEIGHT + BAR_GAP));
</script>

<div class="timeline-tool-row" style="height: {totalHeight}px; position: relative;">
	{#each laidOut as tc}
		{@const x = timeScale(tc.start_ts)}
		{@const x2 = timeScale(tc.end_ts)}
		{@const width = Math.max(x2 - x, MIN_BAR_WIDTH)}
		{@const y = tc.lane * (BAR_HEIGHT + BAR_GAP)}
		{@const outlier = isOutlier(tc)}
		<button
			class="tool-bar"
			style="
				left: {x}px;
				top: {y}px;
				width: {width}px;
				height: {BAR_HEIGHT}px;
				background: {barColor(tc)};
				{outlier ? 'border-left: 2px solid #EE9B00;' : ''}
			"
			title="{tc.name} — {tc.duration_ms}ms ({tc.status})"
			onclick={() => handleBarClick(tc)}
		>
			{#if width > LABEL_MIN_WIDTH}
				<span class="tool-bar-label">{tc.name}</span>
			{/if}
		</button>
	{/each}
</div>

<style>
	.timeline-tool-row {
		width: 100%;
		overflow: hidden;
	}

	.tool-bar {
		position: absolute;
		border: none;
		border-radius: 2px;
		cursor: pointer;
		padding: 0 4px;
		display: flex;
		align-items: center;
		opacity: 0.85;
		transition: opacity 0.1s;
	}

	.tool-bar:hover {
		opacity: 1;
	}

	.tool-bar-label {
		font-size: 10px;
		font-family: 'JetBrains Mono', monospace;
		color: #0D1B2A;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
