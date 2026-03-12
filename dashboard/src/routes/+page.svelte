<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	onMount(() => {
		goto('/tree');
	});
</script>

<div class="flex items-center justify-center h-full" style="color: var(--color-text-muted);">
	Redirecting...
</div>
