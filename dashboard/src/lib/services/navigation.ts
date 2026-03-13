import { goto } from '$app/navigation';

export function navigateToAgent(agentId: string): void {
	goto(`/tree?agent=${encodeURIComponent(agentId)}`);
}

export function navigateToToolFeed(agentId?: string): void {
	if (agentId) {
		goto(`/tools?agent=${encodeURIComponent(agentId)}`);
	} else {
		goto('/tools');
	}
}

export function navigateToTimeline(agentId?: string, toolUseId?: string): void {
	const params = new URLSearchParams();
	if (agentId) params.set('agent', agentId);
	if (toolUseId) params.set('tool', toolUseId);
	const query = params.toString();
	goto(`/timeline${query ? '?' + query : ''}`);
}

/**
 * Get the current agent ID from the page URL, if any.
 * Useful for the F key shortcut to preserve agent context.
 */
export function getAgentFromUrl(): string | null {
	if (typeof window === 'undefined') return null;
	return new URLSearchParams(window.location.search).get('agent');
}
