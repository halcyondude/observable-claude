<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import ToolStrip from './ToolStrip.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/ToolStrip',
		component: ToolStrip,
		tags: ['autodocs'],
	});

	function makeCalls(count, families = ['file', 'exec', 'agent', 'mcp', 'meta'], failRate = 0) {
		return Array.from({ length: count }, (_, i) => ({
			family: families[i % families.length],
			status: Math.random() < failRate ? 'failed' : 'success',
		}));
	}
</script>

<Story name="Empty" args={{ calls: [] }}>
	{#snippet children(args)}
		<ToolStrip {...args} />
	{/snippet}
</Story>

<Story name="Short (5 calls)" args={{ calls: makeCalls(5) }}>
	{#snippet children(args)}
		<ToolStrip {...args} />
	{/snippet}
</Story>

<Story name="Long with overflow (60 calls)" args={{ calls: makeCalls(60), maxPips: 48 }}>
	{#snippet children(args)}
		<ToolStrip {...args} />
	{/snippet}
</Story>

<Story name="With failures" args={{ calls: makeCalls(20, ['file', 'exec', 'agent'], 0.3) }}>
	{#snippet children(args)}
		<ToolStrip {...args} />
	{/snippet}
</Story>

<Story name="Single family (all file)" args={{ calls: makeCalls(15, ['file']) }}>
	{#snippet children(args)}
		<ToolStrip {...args} />
	{/snippet}
</Story>

<Story name="Mixed families" args={{ calls: makeCalls(25) }}>
	{#snippet children(args)}
		<ToolStrip {...args} />
	{/snippet}
</Story>
