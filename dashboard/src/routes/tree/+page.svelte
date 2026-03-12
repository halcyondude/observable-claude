<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import NodeDetail from '$lib/components/NodeDetail.svelte';
	import ToolPipRing from '$lib/components/ToolPipRing.svelte';
	import { activeSessionId } from '$lib/stores/session';
	import { events } from '$lib/stores/events';
	import { fetchSessionGraph, fetchEvents } from '$lib/services/api';
	import type { GraphNode, SessionGraph, ObserverEvent } from '$lib/types/events';

	let container: HTMLDivElement;
	let cy: any = null;
	let selectedNode = $state<GraphNode | null>(null);
	let userPanned = false;
	let graphData = $state<SessionGraph | null>(null);

	// Tool call data per agent, keyed by agent_id
	let agentToolCalls = $state<Record<string, Array<{ name: string; status: string; duration_ms?: number }>>>({});

	// SVG overlay state — tracks rendered node positions for pip rings
	let nodePositions = $state<Array<{ id: string; x: number; y: number; w: number; h: number }>>([]);
	let currentZoom = $state(1);
	let svgOverlay: SVGSVGElement;

	// Tool calls for the currently selected node
	const selectedNodeToolCalls = $derived(
		selectedNode ? (agentToolCalls[selectedNode.data.id] ?? []) : []
	);

	async function loadCytoscape() {
		const cytoscapeModule = await import('cytoscape');
		const cytoscape = cytoscapeModule.default;
		const dagreModule = await import('cytoscape-dagre');
		const dagre = dagreModule.default;
		cytoscape.use(dagre);
		return cytoscape;
	}

	function statusColor(status: string): string {
		switch (status) {
			case 'running': return '#0A9396';
			case 'complete': return '#1E293B';
			case 'failed': return '#CA6702';
			default: return '#0D1B2A';
		}
	}

	function statusTextColor(status: string): string {
		switch (status) {
			case 'running': return '#FFFFFF';
			case 'complete': return '#64748B';
			case 'failed': return '#FFFFFF';
			default: return '#F4F8FB';
		}
	}

	/** Extract tool calls per agent from PostToolUse events */
	function extractToolCalls(toolEvents: ObserverEvent[]): Record<string, Array<{ name: string; status: string; duration_ms?: number }>> {
		const result: Record<string, Array<{ name: string; status: string; duration_ms?: number }>> = {};
		for (const evt of toolEvents) {
			const agentId = evt.agent_id;
			if (!agentId) continue;
			if (!result[agentId]) result[agentId] = [];

			const status = evt.event_type === 'PostToolUseFailure' ? 'failed' : 'success';
			const duration = evt.payload?.duration_ms as number | undefined;
			result[agentId].push({
				name: evt.tool_name || 'unknown',
				status,
				duration_ms: duration
			});
		}
		return result;
	}

	/** Sync SVG overlay positions with Cytoscape rendered positions */
	function updateOverlayPositions() {
		if (!cy) return;

		currentZoom = cy.zoom();
		const pan = cy.pan();
		const zoom = cy.zoom();

		const positions: Array<{ id: string; x: number; y: number; w: number; h: number }> = [];
		cy.nodes().forEach((node: any) => {
			const pos = node.position();
			const w = node.renderedWidth();
			const h = node.renderedHeight();
			// Convert model position to rendered (screen) position
			const rx = pos.x * zoom + pan.x;
			const ry = pos.y * zoom + pan.y;
			positions.push({
				id: node.id(),
				x: rx,
				y: ry,
				w,
				h
			});
		});
		nodePositions = positions;
	}

	async function initGraph() {
		if (!container) return;
		const cytoscape = await loadCytoscape();

		cy = cytoscape({
			container,
			elements: [],
			style: [
				{
					selector: 'node',
					style: {
						'label': 'data(label)',
						'text-valign': 'center',
						'text-halign': 'center',
						'font-size': '11px',
						'font-family': 'Inter, system-ui, sans-serif',
						'color': '#F4F8FB',
						'background-color': '#1E293B',
						'shape': 'round-rectangle',
						'width': (ele: any) => Math.max(80, Math.min(160, 80 + (ele.data('tool_count') || 0) * 5)),
						'height': 40,
						'border-width': 2,
						'border-color': '#1E3A4A',
						'text-wrap': 'ellipsis',
						'text-max-width': '120px'
					} as any
				},
				{
					selector: 'node[status="running"]',
					style: {
						'background-color': '#0A9396',
						'color': '#FFFFFF',
						'border-color': '#0A9396',
						'border-width': 2
					}
				},
				{
					selector: 'node[status="complete"]',
					style: {
						'background-color': '#1E293B',
						'color': '#64748B',
						'border-color': '#1E3A4A'
					}
				},
				{
					selector: 'node[status="failed"]',
					style: {
						'background-color': '#CA6702',
						'color': '#FFFFFF',
						'border-color': '#CA6702'
					}
				},
				{
					selector: 'node[agent_type="session"]',
					style: {
						'background-color': '#0D1B2A',
						'color': '#F4F8FB',
						'border-color': '#1E3A4A',
						'width': 120,
						'height': 48
					}
				},
				{
					selector: 'edge',
					style: {
						'width': 1.5,
						'line-color': '#0A9396',
						'target-arrow-color': '#0A9396',
						'target-arrow-shape': 'triangle',
						'curve-style': 'bezier',
						'arrow-scale': 0.8
					}
				},
				{
					selector: ':selected',
					style: {
						'border-color': '#F4F8FB',
						'border-width': 3
					}
				}
			],
			layout: { name: 'preset' },
			minZoom: 0.2,
			maxZoom: 3,
			wheelSensitivity: 0.3
		});

		cy.on('tap', 'node', (evt: any) => {
			const data = evt.target.data();
			selectedNode = {
				data: {
					id: data.id,
					label: data.label || data.agent_type,
					agent_type: data.agent_type,
					status: data.status,
					tool_count: data.tool_count || 0,
					started_at: data.started_at,
					prompt: data.prompt,
					spawned_by: data.spawned_by,
					skills: data.skills,
					tools: data.tools
				}
			};
		});

		cy.on('tap', (evt: any) => {
			if (evt.target === cy) {
				selectedNode = null;
			}
		});

		cy.on('viewport', () => {
			userPanned = true;
			updateOverlayPositions();
		});

		// Update overlay when layout finishes or nodes move
		cy.on('layoutstop', () => {
			updateOverlayPositions();
		});

		cy.on('position', 'node', () => {
			updateOverlayPositions();
		});
	}

	function updateGraph(data: SessionGraph) {
		if (!cy) return;

		const existingIds = new Set(cy.nodes().map((n: any) => n.id()));

		for (const node of data.nodes) {
			if (existingIds.has(node.data.id)) {
				cy.getElementById(node.data.id).data(node.data);
			} else {
				cy.add({ group: 'nodes', data: node.data });
			}
		}

		const existingEdgeIds = new Set(cy.edges().map((e: any) => e.id()));
		for (const edge of data.edges) {
			if (!existingEdgeIds.has(edge.data.id)) {
				cy.add({ group: 'edges', data: edge.data });
			}
		}

		if (!userPanned || !existingIds.size) {
			runLayout();
		}

		// Deferred position update for when layout hasn't changed
		requestAnimationFrame(() => updateOverlayPositions());
	}

	function runLayout() {
		if (!cy || cy.nodes().length === 0) return;
		cy.layout({
			name: 'dagre',
			rankDir: 'TB',
			nodeSep: 40,
			rankSep: 60,
			animate: true,
			animationDuration: 300
		} as any).run();
	}

	/** Fetch tool call events for the current session */
	async function loadToolCalls(sessionId: string) {
		try {
			// Fetch both PostToolUse and PostToolUseFailure events
			const [successEvents, failureEvents] = await Promise.all([
				fetchEvents({ session_id: sessionId, event_type: 'PostToolUse', limit: 5000 }),
				fetchEvents({ session_id: sessionId, event_type: 'PostToolUseFailure', limit: 1000 })
			]);
			const allToolEvents = [...successEvents, ...failureEvents]
				.sort((a, b) => new Date(a.received_at).getTime() - new Date(b.received_at).getTime());
			agentToolCalls = extractToolCalls(allToolEvents);
		} catch {
			// If event fetch fails, we still have graph data — tool calls just won't show
			agentToolCalls = {};
		}
	}

	function zoomIn() { cy?.zoom(cy.zoom() * 1.3); }
	function zoomOut() { cy?.zoom(cy.zoom() / 1.3); }
	function fit() { cy?.fit(undefined, 40); userPanned = false; }
	function resetLayout() { userPanned = false; runLayout(); }

	// Handle pip click — open detail panel for that agent
	function handlePipClick(agentId: string) {
		if (!cy) return;
		const node = cy.getElementById(agentId);
		if (node && node.length > 0) {
			const data = node.data();
			selectedNode = {
				data: {
					id: data.id,
					label: data.label || data.agent_type,
					agent_type: data.agent_type,
					status: data.status,
					tool_count: data.tool_count || 0,
					started_at: data.started_at,
					prompt: data.prompt,
					spawned_by: data.spawned_by,
					skills: data.skills,
					tools: data.tools
				}
			};
		}
	}

	onMount(() => {
		initGraph();
	});

	$effect(() => {
		const sessionId = $activeSessionId;
		if (sessionId && cy) {
			fetchSessionGraph(sessionId).then((data) => {
				graphData = data;
				updateGraph(data);
			}).catch(() => {});
			loadToolCalls(sessionId);
		}
	});

	$effect(() => {
		const allEvents = $events;
		if (allEvents.length > 0 && $activeSessionId) {
			const latest = allEvents[0];
			if (latest.session_id === $activeSessionId) {
				if (
					latest.event_type === 'SubagentStart' ||
					latest.event_type === 'SubagentEnd'
				) {
					fetchSessionGraph($activeSessionId).then((data) => {
						graphData = data;
						updateGraph(data);
					}).catch(() => {});
				}
				// Refresh tool calls on any tool use event
				if (
					latest.event_type === 'PostToolUse' ||
					latest.event_type === 'PostToolUseFailure'
				) {
					loadToolCalls($activeSessionId);
				}
			}
		}
	});

	onDestroy(() => {
		cy?.destroy();
	});
</script>

<div class="relative w-full h-full">
	<div bind:this={container} class="w-full h-full" style="background: var(--color-bg);"></div>

	<!-- SVG overlay for pip rings — positioned exactly over the Cytoscape canvas -->
	{#if currentZoom >= 0.6}
		<svg
			bind:this={svgOverlay}
			class="absolute inset-0 w-full h-full pointer-events-none z-[5]"
			style="overflow: visible;"
		>
			{#each nodePositions as np (np.id)}
				{#if agentToolCalls[np.id]?.length}
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_static_element_interactions -->
					<g
						style="pointer-events: auto; cursor: pointer;"
						onclick={() => handlePipClick(np.id)}
					>
						<ToolPipRing
							toolCalls={agentToolCalls[np.id]}
							centerX={np.x}
							centerY={np.y}
							radius={np.w / 2 + 8}
						/>
					</g>
				{/if}
			{/each}
		</svg>
	{/if}

	<!-- Floating controls -->
	<div
		class="absolute top-4 right-4 flex flex-col gap-1 z-10"
	>
		{#each [
			{ label: '+', action: zoomIn },
			{ label: '\u2212', action: zoomOut },
			{ label: 'Fit', action: fit },
			{ label: 'Reset', action: resetLayout }
		] as btn}
			<button
				onclick={btn.action}
				class="w-8 h-8 rounded flex items-center justify-center text-xs cursor-pointer border-none"
				style="background: var(--color-surface); color: var(--color-text); border: 1px solid var(--color-border);"
			>
				{btn.label}
			</button>
		{/each}
	</div>

	<!-- Legend -->
	<div
		class="absolute bottom-4 left-4 p-3 rounded-lg z-10 text-xs space-y-1.5"
		style="background: var(--color-surface); border: 1px solid var(--color-border);"
	>
		{#each [
			{ label: 'Running', color: '#0A9396' },
			{ label: 'Complete', color: '#1E293B', border: '#1E3A4A' },
			{ label: 'Failed', color: '#CA6702' },
			{ label: 'Session', color: '#0D1B2A', border: '#1E3A4A' }
		] as item}
			<div class="flex items-center gap-2">
				<span
					class="w-3 h-3 rounded-sm inline-block"
					style="background: {item.color}; {item.border ? `border: 1px solid ${item.border}` : ''}"
				></span>
				<span style="color: var(--color-text-muted);">{item.label}</span>
			</div>
		{/each}
	</div>

	<NodeDetail
		node={selectedNode}
		onclose={() => selectedNode = null}
		toolCalls={selectedNodeToolCalls}
	/>
</div>
