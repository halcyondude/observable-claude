<script lang="ts">
	let {
		playing = false,
		speed = 1,
		progress = 0,
		totalEvents = 0,
		currentEvent = 0,
		onplay = () => {},
		onpause = () => {},
		onseek = (_pos: number) => {},
		onspeed = (_speed: number) => {},
	}: {
		playing?: boolean;
		speed?: number;
		progress?: number;
		totalEvents?: number;
		currentEvent?: number;
		onplay?: () => void;
		onpause?: () => void;
		onseek?: (pos: number) => void;
		onspeed?: (speed: number) => void;
	} = $props();

	const speeds = [0.5, 1, 2, 5, 10];
</script>

<div
	class="flex items-center gap-3 px-4 rounded-lg"
	style="height: 48px; background: var(--color-surface); border: 1px solid var(--color-border);"
>
	<button
		class="cursor-pointer border-none rounded px-2 py-1 text-sm font-medium"
		style="background: var(--color-primary); color: white;"
		onclick={() => playing ? onpause() : onplay()}
	>
		{playing ? '⏸' : '▶'}
	</button>

	<div class="flex-1 relative" style="height: 6px;">
		<div
			class="absolute inset-0 rounded-full"
			style="background: var(--color-surface-2);"
		></div>
		<div
			class="absolute top-0 left-0 bottom-0 rounded-full"
			style="background: var(--color-primary); width: {progress}%;"
		></div>
		<input
			type="range"
			min="0"
			max="100"
			value={progress}
			class="absolute inset-0 w-full opacity-0 cursor-pointer"
			oninput={(e) => onseek(Number((e.target as HTMLInputElement).value))}
		/>
	</div>

	<span class="text-xs font-mono shrink-0" style="color: var(--color-text-muted);">
		{currentEvent}/{totalEvents}
	</span>

	<div class="flex items-center gap-1">
		{#each speeds as s (s)}
			<button
				class="cursor-pointer border-none rounded px-1.5 py-0.5 text-xs font-mono"
				style="
					background: {speed === s ? 'var(--color-primary)' : 'var(--color-surface-2)'};
					color: {speed === s ? 'white' : 'var(--color-text-muted)'};
				"
				onclick={() => onspeed(s)}
			>{s}x</button>
		{/each}
	</div>
</div>
