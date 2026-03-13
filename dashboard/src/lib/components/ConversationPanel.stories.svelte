<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import ConversationPanel from './ConversationPanel.svelte';

	const { Story } = defineMeta({
		title: 'Composite/ConversationPanel',
		component: ConversationPanel,
		tags: ['autodocs'],
	});

	const now = Date.now();

	const userAssistant = [
		{
			id: 'msg-1',
			role: 'user',
			content: 'Implement the StatCard component with support for labels, values, subtitles, and delta indicators.',
			timestamp: new Date(now - 60000).toISOString(),
		},
		{
			id: 'msg-2',
			role: 'assistant',
			content: "I'll create the StatCard component. Let me first read the existing design tokens from app.css to ensure consistency.\n\nThe component will accept:\n- `label` — top label text\n- `value` — the main displayed value\n- `subtitle` — optional secondary text\n- `delta` — optional change indicator\n- `deltaColor` — color for the delta text",
			timestamp: new Date(now - 55000).toISOString(),
		},
	];

	const withToolMessages = [
		...userAssistant,
		{
			id: 'msg-3',
			role: 'tool',
			content: "     1  @import 'tailwindcss';\n     2  \n     3  :root {\n     4    --color-primary: #0A9396;\n     5    --color-bg: #0D1B2A;",
			timestamp: new Date(now - 50000).toISOString(),
			toolName: 'Read',
		},
		{
			id: 'msg-4',
			role: 'assistant',
			content: 'I can see the design tokens. Let me create the StatCard component now.',
			timestamp: new Date(now - 45000).toISOString(),
		},
		{
			id: 'msg-5',
			role: 'tool',
			content: 'File created successfully at: /src/lib/components/StatCard.svelte',
			timestamp: new Date(now - 40000).toISOString(),
			toolName: 'Write',
		},
	];

	const withSynthetic = [
		{
			id: 'msg-s1',
			role: 'user',
			content: 'Fix the layout bug in the sidebar.',
			timestamp: new Date(now - 120000).toISOString(),
		},
		{
			id: 'msg-s2',
			role: 'assistant',
			content: 'Looking at the sidebar component to identify the layout issue.',
			timestamp: new Date(now - 115000).toISOString(),
			synthetic: true,
		},
		{
			id: 'msg-s3',
			role: 'tool',
			content: 'Read /src/lib/components/Sidebar.svelte',
			timestamp: new Date(now - 110000).toISOString(),
			toolName: 'Read',
			synthetic: true,
		},
	];

	const longContent = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '.repeat(30);
	const withLongMessages = [
		{
			id: 'msg-l1',
			role: 'user',
			content: 'Here is a very long message for testing the Show more/less toggle.',
			timestamp: new Date(now - 30000).toISOString(),
		},
		{
			id: 'msg-l2',
			role: 'assistant',
			content: `This is a very long response that should be truncated in the preview. ${longContent}`,
			timestamp: new Date(now - 25000).toISOString(),
		},
	];
</script>

<Story name="Empty" args={{ messages: [] }}>
	{#snippet children(args)}
		<div style="max-width: 500px;">
			<ConversationPanel {...args} />
		</div>
	{/snippet}
</Story>

<Story name="User + Assistant" args={{ messages: userAssistant }}>
	{#snippet children(args)}
		<div style="max-width: 500px;">
			<ConversationPanel {...args} />
		</div>
	{/snippet}
</Story>

<Story name="With tool messages" args={{ messages: withToolMessages }}>
	{#snippet children(args)}
		<div style="max-width: 500px;">
			<ConversationPanel {...args} />
		</div>
	{/snippet}
</Story>

<Story name="With synthetic messages" args={{ messages: withSynthetic }}>
	{#snippet children(args)}
		<div style="max-width: 500px;">
			<ConversationPanel {...args} />
		</div>
	{/snippet}
</Story>

<Story name="Long messages" args={{ messages: withLongMessages }}>
	{#snippet children(args)}
		<div style="max-width: 500px;">
			<ConversationPanel {...args} />
		</div>
	{/snippet}
</Story>
