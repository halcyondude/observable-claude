<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import ToolFamilyBar from './ToolFamilyBar.svelte';

	const { Story } = defineMeta({
		title: 'Atoms/ToolFamilyBar',
		component: ToolFamilyBar,
		tags: ['autodocs'],
	});
</script>

<Story
	name="Single family"
	args={{
		families: [{ family: 'file', total: 42, failed: 0 }],
	}}
>
	{#snippet children(args)}
		<div style="max-width: 400px;">
			<ToolFamilyBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Mixed families"
	args={{
		families: [
			{ family: 'file', total: 30, failed: 0 },
			{ family: 'exec', total: 18, failed: 0 },
			{ family: 'agent', total: 8, failed: 0 },
			{ family: 'mcp', total: 12, failed: 0 },
			{ family: 'meta', total: 5, failed: 0 },
		],
	}}
>
	{#snippet children(args)}
		<div style="max-width: 400px;">
			<ToolFamilyBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="With failures"
	args={{
		families: [
			{ family: 'file', total: 25, failed: 3 },
			{ family: 'exec', total: 15, failed: 5 },
			{ family: 'agent', total: 6, failed: 1 },
			{ family: 'mcp', total: 10, failed: 2 },
		],
	}}
>
	{#snippet children(args)}
		<div style="max-width: 400px;">
			<ToolFamilyBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Heavy exec usage"
	args={{
		families: [
			{ family: 'file', total: 5, failed: 0 },
			{ family: 'exec', total: 80, failed: 12 },
			{ family: 'agent', total: 2, failed: 0 },
		],
	}}
>
	{#snippet children(args)}
		<div style="max-width: 400px;">
			<ToolFamilyBar {...args} />
		</div>
	{/snippet}
</Story>
