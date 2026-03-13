<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import GalaxySessionBar from './GalaxySessionBar.svelte';

	const { Story } = defineMeta({
		title: 'Composite/GalaxySessionBar',
		component: GalaxySessionBar,
		tags: ['autodocs'],
		argTypes: {
			status: { control: 'select', options: ['running', 'complete', 'failed'] },
			saved: { control: 'boolean' },
			eventCount: { control: 'number' },
		},
	});

	function noop() {}
</script>

<Story
	name="Active (running)"
	args={{
		sessionId: 'sess-abc123def',
		status: 'running',
		eventCount: 42,
		duration: '3m 22s',
		onclick: noop,
		onsave: noop,
	}}
>
	{#snippet children(args)}
		<div style="max-width: 300px;">
			<GalaxySessionBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Completed"
	args={{
		sessionId: 'sess-xyz789',
		status: 'complete',
		eventCount: 187,
		duration: '12m 45s',
		onclick: noop,
		onsave: noop,
	}}
>
	{#snippet children(args)}
		<div style="max-width: 300px;">
			<GalaxySessionBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Failed"
	args={{
		sessionId: 'sess-fail001',
		status: 'failed',
		eventCount: 8,
		duration: '0m 12s',
		onclick: noop,
		onsave: noop,
	}}
>
	{#snippet children(args)}
		<div style="max-width: 300px;">
			<GalaxySessionBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Saved"
	args={{
		sessionId: 'sess-saved42',
		status: 'complete',
		eventCount: 95,
		duration: '7m 30s',
		saved: true,
		onclick: noop,
		onsave: noop,
	}}
>
	{#snippet children(args)}
		<div style="max-width: 300px;">
			<GalaxySessionBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Narrow"
	args={{
		sessionId: 'sess-narrow',
		status: 'running',
		eventCount: 10,
		duration: '1m',
		onclick: noop,
		onsave: noop,
	}}
>
	{#snippet children(args)}
		<div style="max-width: 180px;">
			<GalaxySessionBar {...args} />
		</div>
	{/snippet}
</Story>

<Story
	name="Wide"
	args={{
		sessionId: 'sess-wide-container',
		status: 'complete',
		eventCount: 312,
		duration: '25m 18s',
		saved: true,
		onclick: noop,
		onsave: noop,
	}}
>
	{#snippet children(args)}
		<div style="max-width: 500px;">
			<GalaxySessionBar {...args} />
		</div>
	{/snippet}
</Story>
