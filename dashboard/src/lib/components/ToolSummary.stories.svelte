<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import ToolSummary from './ToolSummary.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/ToolSummary',
		component: ToolSummary,
		tags: ['autodocs'],
		argTypes: {
			totalCalls: { control: 'number' },
			successCount: { control: 'number' },
			failCount: { control: 'number' },
		},
	});
</script>

<Story name="High success (>95%)" args={{ totalCalls: 200, successCount: 198, failCount: 2 }}>
	{#snippet children(args)}
		<div style="max-width: 360px;">
			<ToolSummary {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Medium success (80-95%)" args={{ totalCalls: 100, successCount: 87, failCount: 13 }}>
	{#snippet children(args)}
		<div style="max-width: 360px;">
			<ToolSummary {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Low success (<80%)" args={{ totalCalls: 50, successCount: 35, failCount: 15 }}>
	{#snippet children(args)}
		<div style="max-width: 360px;">
			<ToolSummary {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Zero calls" args={{ totalCalls: 0, successCount: 0, failCount: 0 }}>
	{#snippet children(args)}
		<div style="max-width: 360px;">
			<ToolSummary {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Perfect score" args={{ totalCalls: 150, successCount: 150, failCount: 0 }}>
	{#snippet children(args)}
		<div style="max-width: 360px;">
			<ToolSummary {...args} />
		</div>
	{/snippet}
</Story>
