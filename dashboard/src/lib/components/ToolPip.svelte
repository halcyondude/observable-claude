<script lang="ts">
	import { getToolColor } from '$lib/stores/tool-families';

	let {
		toolName,
		status = 'success',
		size = 8
	}: {
		toolName: string;
		status?: 'success' | 'failed' | 'pending';
		size?: number;
	} = $props();

	const color = $derived(getToolColor(toolName));

	const style = $derived.by(() => {
		const base = `width: ${size}px; height: ${size}px; border-radius: 50%; flex-shrink: 0;`;

		if (status === 'failed') {
			return `${base} background: ${color}; box-shadow: 0 0 0 1px var(--color-error);`;
		}
		if (status === 'pending') {
			return `${base} background: ${color}; opacity: 0.4; animation: pulse-pip 2s ease-in-out infinite;`;
		}
		return `${base} background: ${color};`;
	});
</script>

<span
	class="inline-block"
	{style}
	title="{toolName} ({status})"
	role="img"
	aria-label="{toolName} {status}"
></span>
