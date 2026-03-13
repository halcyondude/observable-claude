<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import ToolPip from './ToolPip.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/ToolPip',
		component: ToolPip,
		tags: ['autodocs'],
		argTypes: {
			family: {
				control: 'select',
				options: ['file', 'exec', 'agent', 'mcp', 'meta'],
			},
			status: {
				control: 'select',
				options: ['success', 'failed', 'pending'],
			},
			size: {
				control: { type: 'number', min: 4, max: 24 },
			},
		},
	});
</script>

<Story name="File — Success" args={{ family: 'file', status: 'success', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Exec — Success" args={{ family: 'exec', status: 'success', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Agent — Success" args={{ family: 'agent', status: 'success', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="MCP — Success" args={{ family: 'mcp', status: 'success', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Meta — Success" args={{ family: 'meta', status: 'success', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="File — Failed" args={{ family: 'file', status: 'failed', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Exec — Pending" args={{ family: 'exec', status: 'pending', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Size 6px" args={{ family: 'file', status: 'success', size: 6 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Size 8px (default)" args={{ family: 'file', status: 'success', size: 8 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="Size 14px" args={{ family: 'file', status: 'success', size: 14 }}>
	{#snippet children(args)}
		<ToolPip {...args} />
	{/snippet}
</Story>

<Story name="All Families">
	{#snippet children()}
		<div style="display: flex; gap: 8px; align-items: center;">
			<ToolPip family="file" status="success" />
			<ToolPip family="exec" status="success" />
			<ToolPip family="agent" status="success" />
			<ToolPip family="mcp" status="success" />
			<ToolPip family="meta" status="success" />
		</div>
	{/snippet}
</Story>
