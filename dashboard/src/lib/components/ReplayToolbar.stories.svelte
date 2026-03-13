<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import ReplayToolbar from './ReplayToolbar.svelte';

	const { Story } = defineMeta({
		title: 'Composite/ReplayToolbar',
		component: ReplayToolbar,
		tags: ['autodocs'],
		argTypes: {
			playing: { control: 'boolean' },
			speed: { control: { type: 'select' }, options: [0.5, 1, 2, 5, 10] },
			progress: { control: { type: 'range', min: 0, max: 100 } },
			totalEvents: { control: 'number' },
			currentEvent: { control: 'number' },
		},
	});
</script>

<Story
	name="Paused at start"
	args={{ playing: false, speed: 1, progress: 0, totalEvents: 150, currentEvent: 0 }}
>
	{#snippet children(args)}
		<div style="max-width: 600px;">
			<ReplayToolbar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Playing at 1x"
	args={{ playing: true, speed: 1, progress: 35, totalEvents: 150, currentEvent: 52 }}
>
	{#snippet children(args)}
		<div style="max-width: 600px;">
			<ReplayToolbar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Playing at 5x"
	args={{ playing: true, speed: 5, progress: 50, totalEvents: 200, currentEvent: 100 }}
>
	{#snippet children(args)}
		<div style="max-width: 600px;">
			<ReplayToolbar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Paused near end"
	args={{ playing: false, speed: 2, progress: 92, totalEvents: 80, currentEvent: 74 }}
>
	{#snippet children(args)}
		<div style="max-width: 600px;">
			<ReplayToolbar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Complete"
	args={{ playing: false, speed: 1, progress: 100, totalEvents: 150, currentEvent: 150 }}
>
	{#snippet children(args)}
		<div style="max-width: 600px;">
			<ReplayToolbar {...args} />
		</div>
	{/snippet}
</Story>
