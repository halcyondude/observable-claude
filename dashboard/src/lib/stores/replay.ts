import { writable, derived, get } from 'svelte/store';

export const isReplaying = writable<boolean>(false);
export const replaySessionId = writable<string | null>(null);
export const replaySpeed = writable<number>(1);
export const replayPosition = writable<number>(0);
export const replayTotal = writable<number>(0);
export const replayPaused = writable<boolean>(false);

export const replayProgress = derived(
	[replayPosition, replayTotal],
	([$pos, $total]) => ($total > 0 ? $pos / $total : 0)
);

export function startReplay(sessionId: string): void {
	replaySessionId.set(sessionId);
	isReplaying.set(true);
	replaySpeed.set(1);
	replayPosition.set(0);
	replayTotal.set(0);
	replayPaused.set(false);
}

export function stopReplay(): void {
	isReplaying.set(false);
	replaySessionId.set(null);
	replayPosition.set(0);
	replayTotal.set(0);
	replayPaused.set(false);
}

export function pauseReplay(): void {
	replayPaused.set(true);
}

export function resumeReplay(): void {
	replayPaused.set(false);
}

export function seekReplay(position: number): void {
	replayPosition.set(position);
}

export function setReplaySpeed(speed: number): void {
	replaySpeed.set(speed);
}
