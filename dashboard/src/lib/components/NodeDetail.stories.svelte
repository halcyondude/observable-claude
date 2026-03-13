<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import NodeDetail from './NodeDetail.svelte';

	const { Story } = defineMeta({
		title: 'Composite/NodeDetail',
		component: NodeDetail,
		tags: ['autodocs'],
	});

	function noop() {}

	const runningAgent = {
		data: {
			id: 'agent-abc123def456',
			label: 'main',
			agent_type: 'main',
			status: 'running',
			tool_count: 15,
			started_at: new Date(Date.now() - 120000).toISOString(),
			prompt: 'Implement the dashboard layout with sidebar navigation and top bar. Use the design tokens from app.css.',
			tools: { Read: 8, Write: 4, Bash: 3 },
			skills: ['dev', 'git-workflow'],
		},
	};

	const completedAgent = {
		data: {
			id: 'agent-xyz789',
			label: 'subagent-qa',
			agent_type: 'subagent',
			status: 'complete',
			tool_count: 42,
			started_at: new Date(Date.now() - 600000).toISOString(),
			spawned_by: 'agent-abc123def456',
			tools: { Read: 20, Bash: 12, Write: 8, Grep: 2 },
		},
	};

	const failedAgent = {
		data: {
			id: 'agent-fail001',
			label: 'subagent-build',
			agent_type: 'subagent',
			status: 'failed',
			tool_count: 3,
			started_at: new Date(Date.now() - 30000).toISOString(),
			spawned_by: 'agent-abc123def456',
			tools: { Bash: 3 },
		},
	};

	const emptyAgent = {
		data: {
			id: 'agent-empty',
			label: 'idle',
			agent_type: 'main',
			status: 'running',
			tool_count: 0,
			started_at: new Date().toISOString(),
		},
	};
</script>

<Story name="Running agent with tools" args={{ node: runningAgent, onclose: noop }}>
	{#snippet children(args)}
		<div style="position: relative; min-height: 500px;">
			<NodeDetail {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Completed agent" args={{ node: completedAgent, onclose: noop }}>
	{#snippet children(args)}
		<div style="position: relative; min-height: 500px;">
			<NodeDetail {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Failed agent" args={{ node: failedAgent, onclose: noop }}>
	{#snippet children(args)}
		<div style="position: relative; min-height: 500px;">
			<NodeDetail {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Empty (no tools)" args={{ node: emptyAgent, onclose: noop }}>
	{#snippet children(args)}
		<div style="position: relative; min-height: 500px;">
			<NodeDetail {...args} />
		</div>
	{/snippet}
</Story>

<Story name="No node selected" args={{ node: null, onclose: noop }}>
	{#snippet children(args)}
		<div style="position: relative; min-height: 200px;">
			<NodeDetail {...args} />
			<p style="color: var(--color-text-muted); padding: 24px; font-size: 12px;">
				NodeDetail renders nothing when node is null
			</p>
		</div>
	{/snippet}
</Story>
