<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { timeRange } from '$lib/stores/workspace';
	import type { ActivityData } from '$lib/stores/workspace';

	let {
		activity,
		workspaceColors
	}: {
		activity: ActivityData | null;
		workspaceColors: Map<string, string>;
	} = $props();

	let container: HTMLDivElement;
	let uplot: any = null;
	let brushStart: number | null = null;
	let brushEnd: number | null = null;
	let isDragging = $state(false);
	let dragMode: 'create' | 'move' | 'resize-left' | 'resize-right' | null = null;
	let dragStartX = 0;
	let selectionStartPx = 0;
	let selectionWidthPx = 0;
	let canvasWidth = 0;

	// Selection state as pixel positions within the plot area
	let selLeft = $state<number | null>(null);
	let selRight = $state<number | null>(null);

	function buildData(act: ActivityData): { timestamps: number[]; series: number[][]; workspaceKeys: string[] } {
		if (!act || act.buckets.length === 0) {
			return { timestamps: [], series: [], workspaceKeys: [] };
		}

		const wsKeys = new Set<string>();
		for (const b of act.buckets) {
			for (const k of Object.keys(b.counts)) wsKeys.add(k);
		}
		const workspaceKeys = Array.from(wsKeys);

		const timestamps = act.buckets.map((b) => Math.floor(new Date(b.timestamp).getTime() / 1000));
		const series = workspaceKeys.map((ws) => act.buckets.map((b) => b.counts[ws] ?? 0));

		return { timestamps, series, workspaceKeys };
	}

	function initPlot() {
		if (!container || !activity || activity.buckets.length === 0) return;

		const { timestamps, series, workspaceKeys } = buildData(activity);
		if (timestamps.length === 0) return;

		import('uplot').then((mod) => {
			const uPlot = mod.default;

			// Build stacked fill series
			const plotSeries: any[] = [{}]; // x-axis placeholder
			for (let i = 0; i < workspaceKeys.length; i++) {
				const color = workspaceColors.get(workspaceKeys[i]) ?? '#0A9396';
				plotSeries.push({
					stroke: color,
					fill: color + '66',
					width: 1,
					points: { show: false }
				});
			}

			const data = [timestamps, ...series];

			// Default range: show all data
			const minT = timestamps[0];
			const maxT = timestamps[timestamps.length - 1];

			// Stack the series values for display
			const stackedData = stackSeries(data);

			const opts: any = {
				width: container.clientWidth,
				height: 64,
				cursor: {
					show: true,
					x: true,
					y: false,
					drag: { x: false, y: false }
				},
				select: { show: false },
				legend: { show: false },
				scales: {
					x: { time: true },
					y: { range: (_u: any, _min: number, max: number) => [0, max * 1.1] }
				},
				axes: [
					{
						stroke: '#64748B',
						font: '10px Inter, system-ui',
						grid: { show: false },
						ticks: { show: false }
					},
					{ show: false }
				],
				series: plotSeries
			};

			if (uplot) uplot.destroy();
			uplot = new uPlot(opts, stackedData as any, container);
			canvasWidth = container.clientWidth;

			// Set default time range
			timeRange.set({ start: minT * 1000, end: maxT * 1000 });
		});
	}

	function stackSeries(data: number[][]): number[][] {
		if (data.length <= 2) return data;
		const result: number[][] = [data[0]]; // timestamps
		const accumulated = new Array(data[0].length).fill(0);
		for (let s = 1; s < data.length; s++) {
			const stacked = new Array(data[0].length);
			for (let i = 0; i < data[0].length; i++) {
				accumulated[i] += data[s][i];
				stacked[i] = accumulated[i];
			}
			result.push(stacked);
		}
		return result;
	}

	function getTimeFromX(x: number): number {
		if (!uplot || !activity || activity.buckets.length === 0) return 0;
		const plotLeft = uplot.bbox.left / devicePixelRatio;
		const plotWidth = uplot.bbox.width / devicePixelRatio;
		const frac = Math.max(0, Math.min(1, (x - plotLeft) / plotWidth));
		const { timestamps } = buildData(activity);
		const minT = timestamps[0];
		const maxT = timestamps[timestamps.length - 1];
		return (minT + frac * (maxT - minT)) * 1000;
	}

	function getXFromTime(timeMs: number): number {
		if (!uplot || !activity || activity.buckets.length === 0) return 0;
		const plotLeft = uplot.bbox.left / devicePixelRatio;
		const plotWidth = uplot.bbox.width / devicePixelRatio;
		const { timestamps } = buildData(activity);
		const minT = timestamps[0] * 1000;
		const maxT = timestamps[timestamps.length - 1] * 1000;
		const frac = (timeMs - minT) / (maxT - minT);
		return plotLeft + frac * plotWidth;
	}

	function handleMouseDown(e: MouseEvent) {
		const rect = container.getBoundingClientRect();
		const x = e.clientX - rect.left;

		if (selLeft !== null && selRight !== null) {
			const margin = 6;
			if (Math.abs(x - selLeft) < margin) {
				dragMode = 'resize-left';
			} else if (Math.abs(x - selRight) < margin) {
				dragMode = 'resize-right';
			} else if (x >= selLeft && x <= selRight) {
				dragMode = 'move';
				dragStartX = x;
				selectionStartPx = selLeft;
				selectionWidthPx = selRight - selLeft;
			} else {
				dragMode = 'create';
				selLeft = x;
				selRight = x;
			}
		} else {
			dragMode = 'create';
			selLeft = x;
			selRight = x;
		}

		isDragging = true;
		dragStartX = x;
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isDragging || !dragMode) return;
		const rect = container.getBoundingClientRect();
		const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left));

		if (dragMode === 'create') {
			selRight = x;
		} else if (dragMode === 'move') {
			const delta = x - dragStartX;
			selLeft = Math.max(0, selectionStartPx + delta);
			selRight = Math.min(rect.width, selLeft! + selectionWidthPx);
		} else if (dragMode === 'resize-left') {
			selLeft = Math.min(x, (selRight ?? x) - 10);
		} else if (dragMode === 'resize-right') {
			selRight = Math.max(x, (selLeft ?? 0) + 10);
		}
	}

	function handleMouseUp() {
		if (!isDragging) return;
		isDragging = false;
		dragMode = null;

		if (selLeft !== null && selRight !== null) {
			const left = Math.min(selLeft, selRight);
			const right = Math.max(selLeft, selRight);
			selLeft = left;
			selRight = right;

			if (right - left > 5) {
				const startMs = getTimeFromX(left);
				const endMs = getTimeFromX(right);
				timeRange.set({ start: startMs, end: endMs });
			}
		}
	}

	function handleDblClick() {
		selLeft = null;
		selRight = null;
		if (activity && activity.buckets.length > 0) {
			const { timestamps } = buildData(activity);
			timeRange.set({
				start: timestamps[0] * 1000,
				end: timestamps[timestamps.length - 1] * 1000
			});
		}
	}

	$effect(() => {
		if (activity) {
			initPlot();
		}
	});

	function handleResize() {
		if (uplot && container) {
			uplot.setSize({ width: container.clientWidth, height: 64 });
			canvasWidth = container.clientWidth;
		}
	}

	onMount(() => {
		window.addEventListener('mousemove', handleMouseMove);
		window.addEventListener('mouseup', handleMouseUp);
		window.addEventListener('resize', handleResize);
	});

	onDestroy(() => {
		window.removeEventListener('mousemove', handleMouseMove);
		window.removeEventListener('mouseup', handleMouseUp);
		window.removeEventListener('resize', handleResize);
		uplot?.destroy();
	});
</script>

<div class="relative" style="height: 64px; user-select: none;">
	<div
		bind:this={container}
		class="w-full"
		style="height: 64px;"
		role="slider"
		tabindex="0"
		aria-label="Time range selector"
		aria-valuemin={0}
		aria-valuemax={100}
		aria-valuenow={50}
		onmousedown={handleMouseDown}
		ondblclick={handleDblClick}
	></div>

	{#if selLeft !== null && selRight !== null}
		{@const left = Math.min(selLeft, selRight)}
		{@const width = Math.abs(selRight - selLeft)}
		{#if width > 5}
			<!-- Dimmed regions outside selection -->
			<div
				class="absolute top-0 bottom-0 pointer-events-none"
				style="left: 0; width: {left}px; background: rgba(13, 27, 42, 0.6);"
			></div>
			<div
				class="absolute top-0 bottom-0 pointer-events-none"
				style="left: {left + width}px; right: 0; background: rgba(13, 27, 42, 0.6);"
			></div>
			<!-- Selection border -->
			<div
				class="absolute top-0 bottom-0 pointer-events-none"
				style="left: {left}px; width: {width}px; border: 1px solid var(--color-primary); border-radius: 2px;"
			></div>
			<!-- Resize handles -->
			<div
				class="absolute top-0 bottom-0"
				style="left: {left - 3}px; width: 6px; cursor: ew-resize;"
			></div>
			<div
				class="absolute top-0 bottom-0"
				style="left: {left + width - 3}px; width: 6px; cursor: ew-resize;"
			></div>
		{/if}
	{/if}
</div>
