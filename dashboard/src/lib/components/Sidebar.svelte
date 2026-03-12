<script lang="ts">
	import { page } from '$app/stores';
	import { agentCount, unreadToolCount } from '$lib/stores/events';

	let collapsed = $state(false);
	let autoCollapsed = $state(false);

	const navItems = [
		{ path: '/galaxy', label: 'Galaxy', icon: '\u2726', badgeStore: null },
		{ path: '/tree', label: 'Spawn Tree', icon: '\u25C9', badgeStore: 'agents' },
		{ path: '/timeline', label: 'Timeline', icon: '\u2503', badgeStore: null },
		{ path: '/tools', label: 'Tool Feed', icon: '\u25B6', badgeStore: 'tools' },
		{ path: '/analytics', label: 'Analytics', icon: '\u25A0', badgeStore: null },
		{ path: '/query', label: 'Query', icon: '\u276F', badgeStore: null },
		{ path: '/sessions', label: 'Sessions', icon: '\u25CB', badgeStore: null }
	];

	function checkWidth() {
		if (typeof window !== 'undefined') {
			if (window.innerWidth < 960) {
				autoCollapsed = true;
				collapsed = true;
			} else {
				autoCollapsed = false;
			}
		}
	}

	$effect(() => {
		if (typeof window !== 'undefined') {
			checkWidth();
			window.addEventListener('resize', checkWidth);
			return () => window.removeEventListener('resize', checkWidth);
		}
	});

	function isActive(itemPath: string, currentPath: string): boolean {
		if (itemPath === '/tree' && currentPath === '/') return true;
		if (itemPath === '/galaxy' && currentPath === '/galaxy') return true;
		return currentPath.startsWith(itemPath) && itemPath !== '/galaxy';
	}

	function getBadge(item: typeof navItems[0]): number {
		if (item.badgeStore === 'agents') return $agentCount.active;
		if (item.badgeStore === 'tools') return $unreadToolCount;
		return 0;
	}
</script>

<nav
	class="flex flex-col border-r h-full"
	style="width: {collapsed ? '56px' : '200px'}; background: var(--color-surface); border-color: var(--color-border); transition: width 0.15s ease;"
>
	<div class="flex-1 py-2">
		{#each navItems as item, i}
			{@const active = isActive(item.path, $page.url.pathname)}
			{@const badge = getBadge(item)}
			<a
				href={item.path}
				class="flex items-center gap-3 px-4 py-2.5 text-sm no-underline relative"
				style="color: {active ? 'var(--color-text)' : 'var(--color-text-muted)'}; background: {active ? 'rgba(10, 147, 150, 0.1)' : 'transparent'}; border-left: 3px solid {active ? 'var(--color-primary)' : 'transparent'};"
			>
				<span class="text-base w-5 text-center" style="flex-shrink: 0;">{item.icon}</span>
				{#if !collapsed}
					<span class="flex-1">{item.label}</span>
					{#if badge > 0}
						<span
							class="text-xs px-1.5 py-0.5 rounded-full font-medium"
							style="background: var(--color-primary); color: white; font-size: 10px; min-width: 18px; text-align: center;"
						>
							{badge > 99 ? '99+' : badge}
						</span>
					{/if}
				{/if}
			</a>
		{/each}
	</div>

	{#if !autoCollapsed}
		<button
			onclick={() => collapsed = !collapsed}
			class="p-3 text-xs border-t cursor-pointer border-none"
			style="background: transparent; color: var(--color-text-muted); border-color: var(--color-border);"
		>
			{collapsed ? '\u276F' : '\u276E'}
		</button>
	{/if}
</nav>
