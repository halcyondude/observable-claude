<script lang="ts">
	let {
		label,
		value,
		subtitle = '',
		delta = '',
		deltaColor = 'var(--color-text-muted)'
	}: {
		label: string;
		value: string;
		subtitle?: string;
		delta?: string;
		deltaColor?: string;
	} = $props();
</script>

<div
	class="rounded-lg p-4 flex flex-col justify-between"
	style="background: var(--color-surface); border: 1px solid var(--color-border); height: 88px;"
>
	<span class="text-xs font-medium" style="color: var(--color-text-muted); font-size: 11px;">
		{label}
	</span>
	<div>
		<span class="text-2xl font-bold" style="color: var(--color-text);">
			{value}
		</span>
		{#if subtitle}
			<span class="text-xs ml-2" style="color: var(--color-text-muted);">{subtitle}</span>
		{/if}
	</div>
	{#if delta}
		<span class="text-xs" style="color: {deltaColor}; font-size: 11px;">{delta}</span>
	{/if}
</div>
