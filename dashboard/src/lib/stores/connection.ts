import { writable } from 'svelte/store';
import type { ConnectionStatus } from '$lib/types/events';

export const connectionStatus = writable<ConnectionStatus>('disconnected');
export const reconnectAttempt = writable<number>(0);
