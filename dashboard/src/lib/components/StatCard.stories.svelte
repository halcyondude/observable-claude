<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import StatCard from './StatCard.svelte';

	const { Story } = defineMeta({
		title: 'Composite/StatCard',
		component: StatCard,
		tags: ['autodocs'],
		argTypes: {
			label: { control: 'text' },
			value: { control: 'text' },
			subtitle: { control: 'text' },
			delta: { control: 'text' },
			deltaColor: { control: 'color' },
		},
	});
</script>

<Story
	name="Positive delta"
	args={{
		label: 'Active Agents',
		value: '12',
		subtitle: 'sessions',
		delta: '+3 from yesterday',
		deltaColor: 'var(--color-success)',
	}}
>
	{#snippet children(args)}
		<div style="max-width: 200px;">
			<StatCard {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Negative delta"
	args={{
		label: 'Failures',
		value: '7',
		delta: '-2 from last hour',
		deltaColor: 'var(--color-error)',
	}}
>
	{#snippet children(args)}
		<div style="max-width: 200px;">
			<StatCard {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Large number"
	args={{
		label: 'Total Events',
		value: '12,847',
		subtitle: 'across 23 sessions',
	}}
>
	{#snippet children(args)}
		<div style="max-width: 200px;">
			<StatCard {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Minimal"
	args={{ label: 'Tool Calls', value: '42' }}
>
	{#snippet children(args)}
		<div style="max-width: 200px;">
			<StatCard {...args} />
		</div>
	{/snippet}
</Story>
