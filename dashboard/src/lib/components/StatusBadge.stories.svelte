<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import StatusBadge from './StatusBadge.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/StatusBadge',
		component: StatusBadge,
		tags: ['autodocs'],
		argTypes: {
			status: {
				control: 'select',
				options: ['running', 'complete', 'failed', 'connected', 'disconnected'],
			},
		},
	});
</script>

<Story name="Running" args={{ status: 'running' }}>
	{#snippet children(args)}
		<StatusBadge {...args} />
	{/snippet}
</Story>

<Story name="Complete" args={{ status: 'complete' }}>
	{#snippet children(args)}
		<StatusBadge {...args} />
	{/snippet}
</Story>

<Story name="Failed" args={{ status: 'failed' }}>
	{#snippet children(args)}
		<StatusBadge {...args} />
	{/snippet}
</Story>

<Story name="Connected" args={{ status: 'connected' }}>
	{#snippet children(args)}
		<StatusBadge {...args} />
	{/snippet}
</Story>

<Story name="Disconnected" args={{ status: 'disconnected' }}>
	{#snippet children(args)}
		<StatusBadge {...args} />
	{/snippet}
</Story>

<Story name="All statuses">
	{#snippet children()}
		<div style="display: flex; gap: 12px; flex-wrap: wrap;">
			<StatusBadge status="running" />
			<StatusBadge status="complete" />
			<StatusBadge status="failed" />
			<StatusBadge status="connected" />
			<StatusBadge status="disconnected" />
		</div>
	{/snippet}
</Story>
