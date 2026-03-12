<script lang="ts">
	import { getToolFamilyColor } from '$lib/stores/tool-families';

	let {
		toolName,
		size = 8,
		status = 'success',
		title = ''
	}: {
		toolName: string;
		size?: number;
		status?: 'success' | 'failed' | 'pending';
		title?: string;
	} = $props();

	let color = $derived(getToolFamilyColor(toolName));
</script>

<span
	class="inline-block rounded-full shrink-0"
	style="
		width: {size}px;
		height: {size}px;
		background: {status === 'pending' ? color + '66' : color};
		{status === 'failed' ? `box-shadow: 0 0 0 1px var(--color-error);` : ''}
		{status === 'pending' ? 'animation: pulse-dot 1.5s ease-in-out infinite;' : ''}
	"
	{title}
></span>
