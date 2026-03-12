<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { activeSessionId } from '$lib/stores/session';
	import { events } from '$lib/stores/events';
	import { fetchSessionTimeline } from '$lib/services/api';
	import type { TimelineAgent } from '$lib/types/events';

	let agents = $state<TimelineAgent[]>([]);
	let canvasEl: HTMLCanvasElement;
	let containerEl: HTMLDivElement;
	let animFrame: number;
	let tooltip = $state<{ x: number; y: number; text: string } | null>(null);

	const ROW_HEIGHT = 32;
	const ROW_GAP = 4;
	const LABEL_WIDTH = 200;
	const TICK_WIDTH = 2;
	const TICK_HEIGHT = 12;
	const DEPTH_INDENT = 16;

	function statusColor(status: string): string {
		switch (status) {
			case 'running': return '#0A9396';
			case 'failed': return '#CA6702';
			default: return '#2D3E50';
		}
	}

	function formatTime(ms: number): string {
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}s`;
		if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
		return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
	}

	function chooseInterval(durationMs: number, widthPx: number): number {
		const targetTicks = widthPx / 80;
		const candidates = [1000, 5000, 10000, 30000, 60000, 300000];
		for (const c of candidates) {
			if (durationMs / c <= targetTicks) return c;
		}
		return 300000;
	}

	function draw() {
		if (!canvasEl || !containerEl) return;

		const dpr = window.devicePixelRatio || 1;
		const width = containerEl.clientWidth;
		const totalHeight = Math.max(
			containerEl.clientHeight,
			agents.length * (ROW_HEIGHT + ROW_GAP) + 40
		);

		canvasEl.width = width * dpr;
		canvasEl.height = totalHeight * dpr;
		canvasEl.style.width = `${width}px`;
		canvasEl.style.height = `${totalHeight}px`;

		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;
		ctx.scale(dpr, dpr);
		ctx.clearRect(0, 0, width, totalHeight);

		if (agents.length === 0) {
			ctx.fillStyle = '#64748B';
			ctx.font = '13px Inter, system-ui, sans-serif';
			ctx.textAlign = 'center';
			ctx.fillText('No agents yet', width / 2, totalHeight / 2);
			return;
		}

		const now = Date.now();
		const sessionStart = Math.min(...agents.map((a) => a.start_time));
		const sessionEnd = Math.max(
			now,
			...agents.map((a) => a.end_time ?? now)
		);
		const duration = Math.max(sessionEnd - sessionStart, 1000);
		const chartWidth = width - LABEL_WIDTH;
		const headerHeight = 30;

		// Time axis
		const interval = chooseInterval(duration, chartWidth);
		ctx.fillStyle = '#64748B';
		ctx.font = '10px JetBrains Mono, monospace';
		ctx.textAlign = 'center';
		ctx.strokeStyle = '#1E3A4A';
		ctx.lineWidth = 1;

		for (let t = 0; t <= duration; t += interval) {
			const x = LABEL_WIDTH + (t / duration) * chartWidth;
			ctx.fillText(formatTime(t), x, 12);
			ctx.beginPath();
			ctx.moveTo(x, headerHeight);
			ctx.lineTo(x, totalHeight);
			ctx.stroke();
		}

		// Agent rows
		for (let i = 0; i < agents.length; i++) {
			const agent = agents[i];
			const y = headerHeight + i * (ROW_HEIGHT + ROW_GAP);

			// Label
			ctx.fillStyle = '#64748B';
			ctx.font = '11px Inter, system-ui, sans-serif';
			ctx.textAlign = 'left';
			const indent = agent.depth * DEPTH_INDENT;
			const label = agent.agent_type;
			ctx.fillText(
				label.length > 18 ? label.slice(0, 18) + '...' : label,
				8 + indent,
				y + ROW_HEIGHT / 2 + 4
			);

			// Bar
			const startX = LABEL_WIDTH + ((agent.start_time - sessionStart) / duration) * chartWidth;
			const endTime = agent.end_time ?? now;
			const barWidth = Math.max(2, ((endTime - agent.start_time) / duration) * chartWidth);

			ctx.fillStyle = statusColor(agent.status);
			ctx.beginPath();
			ctx.roundRect(startX, y + 4, barWidth, ROW_HEIGHT - 8, 3);
			ctx.fill();

			// Running bar animated edge
			if (agent.status === 'running') {
				const grad = ctx.createLinearGradient(startX + barWidth - 20, 0, startX + barWidth, 0);
				grad.addColorStop(0, '#0A9396');
				grad.addColorStop(1, 'rgba(10, 147, 150, 0.3)');
				ctx.fillStyle = grad;
				ctx.fillRect(startX + barWidth - 20, y + 4, 20, ROW_HEIGHT - 8);
			}

			// Failed X icon
			if (agent.status === 'failed') {
				ctx.strokeStyle = '#FFFFFF';
				ctx.lineWidth = 1.5;
				const xPos = startX + barWidth - 10;
				const yMid = y + ROW_HEIGHT / 2;
				ctx.beginPath();
				ctx.moveTo(xPos - 3, yMid - 3);
				ctx.lineTo(xPos + 3, yMid + 3);
				ctx.moveTo(xPos + 3, yMid - 3);
				ctx.lineTo(xPos - 3, yMid + 3);
				ctx.stroke();
			}

			// Tool call ticks
			for (const tc of agent.tool_calls) {
				const tickX = LABEL_WIDTH + ((tc.timestamp - sessionStart) / duration) * chartWidth;
				ctx.fillStyle = tc.success ? '#0A9396' : '#CA6702';
				ctx.fillRect(tickX - TICK_WIDTH / 2, y + (ROW_HEIGHT - TICK_HEIGHT) / 2, TICK_WIDTH, TICK_HEIGHT);
			}
		}

		// Current time line
		const nowX = LABEL_WIDTH + ((now - sessionStart) / duration) * chartWidth;
		ctx.strokeStyle = '#0A9396';
		ctx.lineWidth = 1;
		ctx.setLineDash([4, 4]);
		ctx.beginPath();
		ctx.moveTo(nowX, headerHeight);
		ctx.lineTo(nowX, totalHeight);
		ctx.stroke();
		ctx.setLineDash([]);
	}

	function animate() {
		draw();
		animFrame = requestAnimationFrame(animate);
	}

	function handleMouseMove(e: MouseEvent) {
		if (!canvasEl || agents.length === 0) {
			tooltip = null;
			return;
		}

		const rect = canvasEl.getBoundingClientRect();
		const mx = e.clientX - rect.left;
		const my = e.clientY - rect.top;
		const headerHeight = 30;

		const rowIndex = Math.floor((my - headerHeight) / (ROW_HEIGHT + ROW_GAP));
		if (rowIndex >= 0 && rowIndex < agents.length && mx >= LABEL_WIDTH) {
			const agent = agents[rowIndex];
			const dur = agent.end_time
				? formatTime(agent.end_time - agent.start_time)
				: 'running...';
			tooltip = {
				x: e.clientX,
				y: e.clientY,
				text: `${agent.agent_type} (${agent.status}) - ${dur}`
			};
		} else {
			tooltip = null;
		}
	}

	async function loadTimeline(sessionId: string) {
		try {
			agents = await fetchSessionTimeline(sessionId);
		} catch {
			agents = [];
		}
	}

	onMount(() => {
		animate();
	});

	$effect(() => {
		const sid = $activeSessionId;
		if (sid) loadTimeline(sid);
	});

	$effect(() => {
		// Re-fetch on new agent events
		const allEvents = $events;
		if (allEvents.length > 0 && $activeSessionId) {
			const latest = allEvents[0];
			if (
				latest.session_id === $activeSessionId &&
				(latest.event_type === 'SubagentStart' || latest.event_type === 'SubagentEnd')
			) {
				loadTimeline($activeSessionId);
			}
		}
	});

	onDestroy(() => {
		if (animFrame) cancelAnimationFrame(animFrame);
	});
</script>

<div class="relative w-full h-full" bind:this={containerEl}>
	<canvas
		bind:this={canvasEl}
		class="w-full h-full"
		style="background: var(--color-bg);"
		onmousemove={handleMouseMove}
		onmouseleave={() => tooltip = null}
	></canvas>

	{#if tooltip}
		<div
			class="fixed z-50 px-2 py-1 rounded text-xs pointer-events-none"
			style="left: {tooltip.x + 12}px; top: {tooltip.y - 8}px; background: var(--color-surface-2); color: var(--color-text); border: 1px solid var(--color-border);"
		>
			{tooltip.text}
		</div>
	{/if}

	{#if agents.length === 0}
		<div class="absolute inset-0 flex items-center justify-center" style="color: var(--color-text-muted);">
			<span class="text-sm">Waiting for agents...</span>
		</div>
	{/if}
</div>
