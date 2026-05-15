<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth.svelte';
	import { client } from '$lib/api/client';
	import { onMount } from 'svelte';
	import { createQuery } from '@tanstack/svelte-query';
	import { Button } from '$lib/components/ui/button';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { initials } from '$lib/utils';
	import FolderOpen from 'lucide-svelte/icons/folder-open';
	import Settings from 'lucide-svelte/icons/settings';
	import Users from 'lucide-svelte/icons/users';
	import LogOut from 'lucide-svelte/icons/log-out';
	import LogIn from 'lucide-svelte/icons/log-in';

	let { children } = $props();

	const navItems = [
		{ href: '/projects', label: 'Projects', icon: FolderOpen }
	];

	const authNavItems = [
		{ href: '/settings', label: 'Settings', icon: Settings }
	];

	const adminItems = [{ href: '/admin/users', label: 'Users', icon: Users }];

	onMount(async () => {
		if (auth.isAuthenticated && !auth.user) {
			const { data } = await client.GET('/api/users/me');
			if (data) auth.user = data;
		}
	});

	async function handleLogout() {
		const refreshToken = auth.refreshToken;
		if (refreshToken) {
			await client.POST('/api/auth/logout', { body: { refresh_token: refreshToken } });
		}
		auth.clear();
		goto('/login');
	}

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	let currentPath = $derived($page.url.pathname);

	// Extract project ID when on any /projects/[id]/... route
	let activeProjectId = $derived.by(() => {
		const m = currentPath.match(/^\/projects\/([^/]+)/);
		return m ? m[1] : null;
	});

	const activeProject = createQuery(() => ({
		queryKey: ['project', activeProjectId],
		enabled: !!activeProjectId,
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}', {
				params: { path: { project_id: activeProjectId! } }
			});
			if (error) throw error;
			return data;
		}
	}));
</script>

<div class="flex min-h-svh bg-background">
	<!-- Sidebar (desktop) -->
	<aside class="hidden w-56 flex-shrink-0 flex-col border-r bg-card md:flex md:sticky md:top-0 md:h-screen">
		<div class="flex h-14 items-center border-b px-4">
			{#if activeProjectId && activeProject.data}
				{@const p = activeProject.data}
				<a href="/projects/{p.id}" class="flex min-w-0 items-center gap-2">
					{#if p.has_icon}
						<img src="{BASE_URL}/api/projects/{p.id}/icon" alt="" class="size-7 rounded-md object-cover" />
					{/if}
					<span class="truncate font-bold tracking-tight">{p.name}</span>
				</a>
			{:else}
				<span class="font-bold tracking-tight">Localez</span>
			{/if}
		</div>
		<nav class="flex flex-1 flex-col gap-1 p-2">
			{#each navItems as item}
				<a
					href={item.href}
					class="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent
						{currentPath.startsWith(item.href)
						? 'bg-accent font-medium text-accent-foreground'
						: 'text-muted-foreground'}"
				>
					<item.icon size={16} />
					{item.label}
				</a>
			{/each}

			{#if auth.isAuthenticated}
				{#each authNavItems as item}
					<a
						href={item.href}
						class="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent
							{currentPath.startsWith(item.href)
							? 'bg-accent font-medium text-accent-foreground'
							: 'text-muted-foreground'}"
					>
						<item.icon size={16} />
						{item.label}
					</a>
				{/each}

				{#if auth.isAdmin}
					<div class="mt-4 px-3 text-xs font-semibold uppercase text-muted-foreground">Admin</div>
					{#each adminItems as item}
						<a
							href={item.href}
							class="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent
								{currentPath.startsWith(item.href)
								? 'bg-accent font-medium text-accent-foreground'
								: 'text-muted-foreground'}"
						>
							<item.icon size={16} />
							{item.label}
						</a>
					{/each}
				{/if}
			{/if}
		</nav>

		<div class="border-t p-2">
			<div class="mb-2 flex gap-3 px-3 text-xs text-muted-foreground">
				<a href="/legal/imprint" class="hover:text-foreground hover:underline">Imprint</a>
				<a href="/legal/privacy" class="hover:text-foreground hover:underline">Privacy</a>
			</div>
			{#if auth.isAuthenticated}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent"
					>
						<Avatar.Root class="size-6">
							<Avatar.Fallback class="text-xs">
								{auth.user ? initials(auth.user.username) : '?'}
							</Avatar.Fallback>
						</Avatar.Root>
						<span class="truncate">{auth.user?.username ?? '…'}</span>
					</DropdownMenu.Trigger>
					<DropdownMenu.Content align="start" class="w-48">
						<DropdownMenu.Item onclick={handleLogout}>
							<LogOut size={14} class="mr-2" />
							Sign out
						</DropdownMenu.Item>
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			{:else}
				<a href="/login" class="flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">
					<LogIn size={16} />
					Sign in
				</a>
			{/if}
		</div>
	</aside>

	<div class="flex flex-1 flex-col">
		<!-- Mobile header -->
		<header class="flex h-14 items-center border-b px-4 md:hidden">
			{#if activeProjectId && activeProject.data}
				{@const p = activeProject.data}
				<a href="/projects/{p.id}" class="flex items-center gap-2 min-w-0">
					{#if p.has_icon}
						<img src="{BASE_URL}/api/projects/{p.id}/icon" alt="" class="size-7 rounded-md object-cover" />
					{/if}
					<span class="truncate font-bold">{p.name}</span>
				</a>
			{:else}
				<span class="font-bold">Localez</span>
			{/if}
		</header>

		<!-- Mobile bottom tab bar -->
		<nav class="fixed bottom-0 left-0 right-0 z-30 border-t bg-card md:hidden">
			<div class="flex justify-center gap-4 border-b px-4 py-1 text-xs text-muted-foreground">
				<a href="/legal/imprint" class="hover:text-foreground hover:underline">Imprint</a>
				<a href="/legal/privacy" class="hover:text-foreground hover:underline">Privacy</a>
			</div>
			<div class="flex">
				{#each navItems as item}
					<a
						href={item.href}
						class="flex flex-1 flex-col items-center gap-1 py-2 text-xs transition-colors
							{currentPath.startsWith(item.href) ? 'text-foreground' : 'text-muted-foreground'}"
					>
						<item.icon size={20} />
						{item.label}
					</a>
				{/each}

				{#if auth.isAuthenticated}
					{#each authNavItems as item}
						<a
							href={item.href}
							class="flex flex-1 flex-col items-center gap-1 py-2 text-xs transition-colors
								{currentPath.startsWith(item.href) ? 'text-foreground' : 'text-muted-foreground'}"
						>
							<item.icon size={20} />
							{item.label}
						</a>
					{/each}

					{#if auth.isAdmin}
						{#each adminItems as item}
							<a
								href={item.href}
								class="flex flex-1 flex-col items-center gap-1 py-2 text-xs transition-colors
									{currentPath.startsWith(item.href) ? 'text-foreground' : 'text-muted-foreground'}"
							>
								<item.icon size={20} />
								{item.label}
							</a>
						{/each}
					{/if}

					<button
						onclick={handleLogout}
						class="flex flex-1 flex-col items-center gap-1 py-2 text-xs text-muted-foreground transition-colors hover:text-destructive"
					>
						<LogOut size={20} />
						Sign out
					</button>
				{:else}
					<a
						href="/login"
						class="flex flex-1 flex-col items-center gap-1 py-2 text-xs transition-colors
							{currentPath.startsWith('/login') ? 'text-foreground' : 'text-muted-foreground'}"
					>
						<LogIn size={20} />
						Sign in
					</a>
				{/if}
			</div>
		</nav>

		<main class="flex-1 overflow-auto pb-24 md:pb-0">
			{@render children()}
		</main>
	</div>
</div>
