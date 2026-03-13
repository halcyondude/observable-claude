<script lang="ts">
	import { getToolColor } from '$lib/stores/tool-families';

	let {
		toolCalls,
		centerX,
		centerY,
		radius
	}: {
		toolCalls: Array<{ name: string; status: string; duration_ms?: number }>;
		centerX: number;
		centerY: number;
		radius: number;
	} = $props();

	const PIP_SIZE = 4;
	const MAX_PIPS = 24;

	function normalizeStatus(s: string): 'success' | 'failed' | 'pending' {
		if (s === 'failed' || s === 'error') return 'failed';
		if (s === 'pending' || s === 'running') return 'pending';
		return 'success';
	}

	const visibleCalls = $derived(
		toolCalls.length > MAX_PIPS
			? toolCalls.slice(-MAX_PIPS)
			: toolCalls
	);

	const pips = $derived.by(() => {
		const count = visibleCalls.length;
		if (count === 0) return [];
		const angleStep = (2 * Math.PI) / Math.max(count, 1);
		// Start at top (-PI/2) and go clockwise
		return visibleCalls.map((call, i) => {
			const angle = -Math.PI / 2 + i * angleStep;
			const x = centerX + radius * Math.cos(angle);
			const y = centerY + radius * Math.sin(angle);
			const status = normalizeStatus(call.status);
			const color = getToolColor(call.name);
			return { x, y, color, status, call, index: i };
		});
	});

	let hoveredIndex = $state<number | null>(null);
</script>

<g class="tool-pip-ring">
	{#each pips as pip (pip.index)}
		<circle
			cx={pip.x}
			cy={pip.y}
			r={PIP_SIZE / 2}
			fill={pip.color}
			opacity={pip.status === 'pending' ? 0.4 : 1}
			onmouseenter={() => hoveredIndex = pip.index}
			onmouseleave={() => hoveredIndex = null}
			style="cursor: pointer;"
		/>
		{#if pip.status === 'failed'}
			<circle
				cx={pip.x}
				cy={pip.y}
				r={PIP_SIZE / 2 + 1}
				fill="none"
				stroke="var(--color-error)"
				stroke-width="1"
			/>
		{/if}
	{/each}

	<!-- Tooltip on hover -->
	{#if hoveredIndex != null}
		{@const pip = pips[hoveredIndex]}
		{@const tooltipX = pip.x}
		{@const tooltipY = pip.y - 14}
		<g>
			<rect
				x={tooltipX - 50}
				y={tooltipY - 12}
				width="100"
				height="18"
				rx="3"
				fill="var(--color-surface-2)"
				stroke="var(--color-border)"
				stroke-width="0.5"
				opacity="0.95"
			/>
			<text
				x={tooltipX}
				y={tooltipY}
				text-anchor="middle"
				font-size="9"
				font-family="'JetBrains Mono', monospace"
				fill="var(--color-text)"
			>
				{pip.call.name} ({pip.status})
				{#if pip.call.duration_ms}
					 {pip.call.duration_ms}ms
				{/if}
			</text>
		</g>
	{/if}

	<!-- Overflow indicator -->
	{#if toolCalls.length > MAX_PIPS}
		<text
			x={centerX}
			y={centerY + radius + 12}
			text-anchor="middle"
			font-size="8"
			font-family="'JetBrains Mono', monospace"
			fill="var(--color-text-muted)"
		>
			+{toolCalls.length - MAX_PIPS}
		</text>
	{/if}
</g>
