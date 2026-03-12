<script lang="ts">
	import type { ObserverEvent } from '$lib/types/events';

	let { event }: { event: ObserverEvent } = $props();
	let expanded = $state(false);

	function borderColor(type: string): string {
		switch (type) {
			case 'PreToolUse': return 'var(--color-primary)';
			case 'PostToolUse': return 'var(--color-success)';
			case 'PostToolUseFailure': return 'var(--color-error)';
			default: return 'var(--color-border)';
		}
	}

	function pillColor(type: string): { bg: string; text: string } {
		switch (type) {
			case 'PreToolUse': return { bg: 'rgba(10, 147, 150, 0.2)', text: 'var(--color-primary)' };
			case 'PostToolUse': return { bg: 'rgba(148, 210, 189, 0.2)', text: 'var(--color-success)' };
			case 'PostToolUseFailure': return { bg: 'rgba(202, 103, 2, 0.2)', text: 'var(--color-error)' };
			default: return { bg: 'var(--color-surface-2)', text: 'var(--color-text-muted)' };
		}
	}

	function pillLabel(type: string): string {
		switch (type) {
			case 'PreToolUse': return 'PRE';
			case 'PostToolUse': return 'POST';
			case 'PostToolUseFailure': return 'FAIL';
			default: return type;
		}
	}

	function formatTimestamp(ts: string): string {
		const d = new Date(ts);
		return d.toLocaleTimeString('en-US', { hour12: false }) +
			'.' + d.getMilliseconds().toString().padStart(3, '0');
	}

	function getSummary(event: ObserverEvent): string {
		const payload = event.payload as any;
		if (event.tool_name === 'Bash' && payload?.tool_input?.command) {
			const cmd = payload.tool_input.command;
			return cmd.length > 60 ? cmd.slice(0, 60) + '...' : cmd;
		}
		if (event.tool_name === 'Write' && payload?.tool_input?.file_path) {
			return payload.tool_input.file_path;
		}
		if (event.tool_name === 'Read' && payload?.tool_input?.file_path) {
			return payload.tool_input.file_path;
		}
		if (payload?.tool_input) {
			const str = JSON.stringify(payload.tool_input);
			return str.length > 60 ? str.slice(0, 60) + '...' : str;
		}
		return '';
	}

	function getDuration(event: ObserverEvent): string {
		const payload = event.payload as any;
		if (payload?.duration_ms) {
			return `${Math.round(payload.duration_ms)}ms`;
		}
		return '';
	}

	function formatJson(obj: unknown): string {
		try {
			return JSON.stringify(obj, null, 2);
		} catch {
			return String(obj);
		}
	}

	$effect(() => {
		function handleClose() { expanded = false; }
		document.addEventListener('close-panels', handleClose);
		return () => document.removeEventListener('close-panels', handleClose);
	});
</script>

<div
	class="cursor-pointer"
	style="border-left: 4px solid {borderColor(event.event_type)}; background: var(--color-surface);"
	onclick={() => expanded = !expanded}
	onkeydown={(e) => { if (e.key === 'Enter') expanded = !expanded; }}
	role="button"
	tabindex="0"
>
	<div class="flex items-center gap-3 px-3" style="height: 48px;">
		<span class="font-mono text-xs shrink-0" style="color: var(--color-text-muted); width: 80px;">
			{formatTimestamp(event.received_at)}
		</span>

		{#if true}
			{@const pill = pillColor(event.event_type)}
			<span
				class="px-1.5 py-0.5 rounded text-xs font-medium shrink-0"
				style="background: {pill.bg}; color: {pill.text}; font-size: 10px;"
			>
				{pillLabel(event.event_type)}
			</span>
		{/if}

		<span class="text-xs font-semibold shrink-0" style="color: var(--color-text);">
			{event.tool_name ?? ''}
		</span>

		<span class="text-xs shrink-0" style="color: var(--color-text-muted);">
			{event.agent_type ?? ''}
		</span>

		<span class="flex-1 text-xs truncate" style="color: var(--color-text-muted);">
			{getSummary(event)}
		</span>

		{#if event.event_type === 'PostToolUse' || event.event_type === 'PostToolUseFailure'}
			{@const dur = getDuration(event)}
			{#if dur}
				<span class="text-xs font-mono shrink-0" style="color: var(--color-text-muted);">
					{dur}
				</span>
			{/if}
		{/if}
	</div>

	{#if expanded}
		<div
			class="px-4 py-3 border-t text-xs space-y-3"
			style="border-color: var(--color-border); background: var(--color-bg);"
		>
			{#if (event.payload as any)?.tool_input}
				<div>
					<div class="mb-1 font-medium" style="color: var(--color-text-muted);">Input</div>
					<pre class="font-mono text-xs overflow-x-auto p-2 rounded" style="background: var(--color-surface-2); color: var(--color-text); white-space: pre-wrap; word-break: break-all;">{formatJson((event.payload as any).tool_input)}</pre>
				</div>
			{/if}

			{#if (event.payload as any)?.tool_response}
				{@const resp = String((event.payload as any).tool_response)}
				<div>
					<div class="mb-1 font-medium" style="color: var(--color-text-muted);">Response</div>
					<pre class="font-mono text-xs overflow-x-auto p-2 rounded" style="background: var(--color-surface-2); color: var(--color-text); white-space: pre-wrap; word-break: break-all;">{resp.length > 500 ? resp.slice(0, 500) + '...' : resp}</pre>
				</div>
			{/if}

			<div class="flex gap-4" style="color: var(--color-text-muted);">
				{#if event.agent_id}
					<span>Agent: <span class="font-mono">{event.agent_id}</span></span>
				{/if}
				{#if event.tool_use_id}
					<span>Tool Use: <span class="font-mono">{event.tool_use_id}</span></span>
				{/if}
			</div>
		</div>
	{/if}
</div>
