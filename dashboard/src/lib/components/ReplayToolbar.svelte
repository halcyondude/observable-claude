<script lang="ts">
	import {
		isReplaying,
		replaySessionId,
		replaySpeed,
		replayPosition,
		replayTotal,
		replayPaused,
		stopReplay,
		setReplaySpeed
	} from '$lib/stores/replay';
	import { replayControl } from '$lib/services/api';
	import { disconnectReplay } from '$lib/services/sse';

	const SPEEDS = [1, 2, 5, 10, 0];

	function speedLabel(s: number): string {
		return s === 0 ? 'Max' : `${s}x`;
	}

	async function togglePause() {
		const sid = $replaySessionId;
		if (!sid) return;

		if ($replayPaused) {
			await replayControl(sid, 'resume');
			replayPaused.set(false);
		} else {
			await replayControl(sid, 'pause');
			replayPaused.set(true);
		}
	}

	async function handleSpeedChange(speed: number) {
		const sid = $replaySessionId;
		if (!sid) return;

		setReplaySpeed(speed);
		await replayControl(sid, 'speed', { speed });
	}

	async function handleSeek(e: Event) {
		const sid = $replaySessionId;
		if (!sid) return;

		const target = e.target as HTMLInputElement;
		const position = parseInt(target.value, 10);
		replayPosition.set(position);
		await replayControl(sid, 'seek', { position });
	}

	async function handleStop() {
		const sid = $replaySessionId;
		if (sid) {
			await replayControl(sid, 'stop').catch(() => {});
		}
		disconnectReplay();
		stopReplay();
	}

	function formatTimestamp(position: number, total: number): string {
		if (total === 0) return '--:--';
		const pct = position / total;
		const minutes = Math.floor(pct * 100);
		return `${position + 1} of ${total}`;
	}
</script>

{#if $isReplaying}
	<div
		class="fixed bottom-0 left-0 right-0 z-50 flex items-center gap-4 px-6"
		style="height: 64px; background: var(--color-surface); border-top: 1px solid var(--color-border); backdrop-filter: blur(8px);"
	>
		<!-- Play/Pause -->
		<button
			onclick={togglePause}
			class="flex items-center justify-center w-10 h-10 rounded-lg cursor-pointer border-none"
			style="background: var(--color-primary); color: white;"
			title={$replayPaused ? 'Resume' : 'Pause'}
		>
			{#if $replayPaused}
				<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
					<polygon points="4,2 14,8 4,14" />
				</svg>
			{:else}
				<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
					<rect x="3" y="2" width="4" height="12" />
					<rect x="9" y="2" width="4" height="12" />
				</svg>
			{/if}
		</button>

		<!-- Stop -->
		<button
			onclick={handleStop}
			class="flex items-center justify-center w-10 h-10 rounded-lg cursor-pointer border-none"
			style="background: var(--color-surface-2); color: var(--color-text);"
			title="Stop replay"
		>
			<svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
				<rect x="2" y="2" width="10" height="10" rx="1" />
			</svg>
		</button>

		<!-- Speed selector -->
		<div class="flex items-center gap-1">
			{#each SPEEDS as speed}
				<button
					onclick={() => handleSpeedChange(speed)}
					class="px-2.5 py-1.5 rounded text-xs font-mono cursor-pointer border-none"
					style="background: {$replaySpeed === speed ? 'var(--color-primary)' : 'var(--color-surface-2)'}; color: {$replaySpeed === speed ? 'white' : 'var(--color-text-muted)'};"
				>
					{speedLabel(speed)}
				</button>
			{/each}
		</div>

		<!-- Timeline scrubber -->
		<div class="flex-1 flex items-center gap-3">
			<input
				type="range"
				min="0"
				max={Math.max($replayTotal - 1, 0)}
				value={$replayPosition}
				oninput={handleSeek}
				class="flex-1 h-1.5 rounded-full cursor-pointer"
				style="accent-color: var(--color-primary);"
			/>
		</div>

		<!-- Event counter -->
		<div class="text-xs font-mono whitespace-nowrap" style="color: var(--color-text-muted);">
			Event {$replayPosition + 1} of {$replayTotal}
		</div>

		<!-- Replay badge -->
		<div
			class="px-2 py-1 rounded text-xs font-semibold"
			style="background: rgba(10, 147, 150, 0.2); color: var(--color-primary);"
		>
			REPLAY
		</div>
	</div>
{/if}
