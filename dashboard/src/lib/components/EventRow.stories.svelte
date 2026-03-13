<script module>
	import { defineMeta } from '@storybook/addon-svelte-csf';
	import EventRow from './EventRow.svelte';

	const { Story } = defineMeta({
		title: 'Composite/EventRow',
		component: EventRow,
		tags: ['autodocs'],
	});

	const now = new Date().toISOString();

	const preToolUse = {
		event_id: 'evt-abc123',
		event_type: 'PreToolUse',
		session_id: 'sess-001',
		agent_id: 'agent-main',
		agent_type: 'main',
		tool_use_id: 'tu-xyz789',
		tool_name: 'Read',
		cwd: '/Users/dev/project',
		received_at: now,
		payload: {
			tool_input: { file_path: '/src/lib/components/StatCard.svelte' },
		},
	};

	const postToolUse = {
		...preToolUse,
		event_type: 'PostToolUse',
		tool_name: 'Bash',
		payload: {
			tool_input: { command: 'npm run build && npm test -- --reporter verbose' },
			tool_response: 'Build succeeded. 42 tests passed.',
			duration_ms: 3420,
		},
	};

	const postToolUseFailure = {
		...preToolUse,
		event_type: 'PostToolUseFailure',
		tool_name: 'Write',
		payload: {
			tool_input: { file_path: '/etc/readonly-file.txt', content: 'test' },
			tool_response: 'Error: EACCES: permission denied',
			duration_ms: 12,
		},
	};

	const sessionStart = {
		...preToolUse,
		event_type: 'SessionStart',
		tool_name: undefined,
		tool_use_id: undefined,
		payload: { cwd: '/Users/dev/project' },
	};
</script>

<Story name="PreToolUse" args={{ event: preToolUse }}>
	{#snippet children(args)}
		<EventRow {...args} />
	{/snippet}
</Story>

<Story name="PostToolUse (success)" args={{ event: postToolUse }}>
	{#snippet children(args)}
		<EventRow {...args} />
	{/snippet}
</Story>

<Story name="PostToolUseFailure" args={{ event: postToolUseFailure }}>
	{#snippet children(args)}
		<EventRow {...args} />
	{/snippet}
</Story>

<Story name="SessionStart" args={{ event: sessionStart }}>
	{#snippet children(args)}
		<EventRow {...args} />
	{/snippet}
</Story>
