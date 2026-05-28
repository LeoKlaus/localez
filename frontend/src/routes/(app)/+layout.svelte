<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth.svelte';
	import { legalStore } from '$lib/stores/legal.svelte';
	import { client } from '$lib/api/client';
	import { onMount } from 'svelte';
	import { createQuery, useQueryClient } from '@tanstack/svelte-query';
	import { Button } from '$lib/components/ui/button';
	import * as Avatar from '$lib/components/ui/avatar';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { initials } from '$lib/utils';
	import FolderOpen from 'lucide-svelte/icons/folder-open';
	import Settings from 'lucide-svelte/icons/settings';
	import Users from 'lucide-svelte/icons/users';
	import LogOut from 'lucide-svelte/icons/log-out';
	import LogIn from 'lucide-svelte/icons/log-in';
	import ClipboardCheck from 'lucide-svelte/icons/clipboard-check';
	import Languages from 'lucide-svelte/icons/languages';

	let { children } = $props();
	const qc = useQueryClient();

	const navItems = [
		{ href: '/projects', label: 'All Projects', icon: FolderOpen }
	];

	const authNavItems = [
		{ href: '/settings', label: 'Settings', icon: Settings }
	];

	const adminItems = [{ href: '/admin/users', label: 'Users', icon: Users }];

	onMount(async () => {
		// If there's no in-memory access token, try to obtain one silently using
		// the HttpOnly refresh-token cookie set during the last login.
		if (!auth.isAuthenticated) {
			const refreshed = await auth.tryRefresh();
			if (refreshed) {
				// The projects query may have already fired without auth and cached
				// public-only results. Invalidate so it re-fetches as an authenticated user.
				qc.invalidateQueries({ queryKey: ['projects'] });
			}
		}
		if (auth.isAuthenticated && !auth.user) {
			const { data } = await client.GET('/api/users/me');
			if (data) auth.user = data;
		}
	});

	async function handleLogout() {
		await fetch('/api/auth/logout/cookie', { method: 'POST' });
		auth.clear();
		qc.clear();
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
			<div class="flex min-w-0 items-center">
				{#if activeProjectId && activeProject.data}
					{@const p = activeProject.data}
					<a href="/projects/{p.id}" class="flex min-w-0 items-center gap-2">
						{#if p.has_icon}
							<img src="{BASE_URL}/api/projects/{p.id}/icon" alt="" class="size-7 rounded-md object-cover" />
						{/if}
						<span class="truncate font-bold tracking-tight">{p.name}</span>
					</a>
				{:else}
					<a href="/projects" class="flex items-center gap-2">
						<img src="/icons/icon.svg" alt="" class="size-7 dark:hidden" aria-hidden="true" />
						<img src="/icons/IconDark.svg" alt="" class="size-7 hidden dark:block" aria-hidden="true" />
						<span class="font-bold tracking-tight">Localez</span>
					</a>
				{/if}
			</div>
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

				{#if activeProjectId}
					<div class="mt-4 px-3 text-xs font-semibold uppercase text-muted-foreground">Project</div>
					<a
						href="/projects/{activeProjectId}"
						class="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent
							{currentPath === `/projects/${activeProjectId}` || currentPath.startsWith(`/projects/${activeProjectId}/strings`)
							? 'bg-accent font-medium text-accent-foreground'
							: 'text-muted-foreground'}"
					>
						<Languages size={16} />
						Strings
					</a>
					{#if auth.isAdmin}
						<a
							href="/projects/{activeProjectId}/review"
							class="flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent
								{currentPath.startsWith(`/projects/${activeProjectId}/review`)
								? 'bg-accent font-medium text-accent-foreground'
								: 'text-muted-foreground'}"
						>
							<ClipboardCheck size={16} />
							Review
						</a>
					{/if}
				{/if}

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
			<a href="https://github.com/leoklaus/localez" target="_blank" rel="noopener noreferrer" class="mt-auto flex items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
				<svg viewBox="0 0 24 24" class="size-4 shrink-0 fill-current" aria-hidden="true"><path d="M12 2C6.477 2 2 6.484 2 12.021c0 4.428 2.865 8.184 6.839 9.504.5.092.682-.217.682-.482 0-.237-.009-.868-.013-1.703-2.782.605-3.369-1.342-3.369-1.342-.454-1.154-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.026 2.747-1.026.546 1.378.202 2.397.1 2.65.64.7 1.028 1.595 1.028 2.688 0 3.848-2.338 4.695-4.566 4.944.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.2 22 16.447 22 12.021 22 6.484 17.523 2 12 2z"/></svg>
				Localez on GitHub
			</a>
		</nav>

		<div class="border-t p-2">
			{#if legalStore.hasImprint || legalStore.hasPrivacy || legalStore.hasContributions}
				<div class="mb-2 flex flex-col gap-1 px-3 text-xs text-muted-foreground">
					{#if legalStore.hasImprint || legalStore.hasPrivacy}
						<div class="flex gap-3">
							{#if legalStore.hasImprint}
								<a href="/legal/imprint" class="hover:text-foreground hover:underline">Imprint</a>
							{/if}
							{#if legalStore.hasPrivacy}
								<a href="/legal/privacy" class="hover:text-foreground hover:underline">Privacy Policy</a>
							{/if}
						</div>
					{/if}
					{#if legalStore.hasContributions}
						<a href="/legal/contributions" class="hover:text-foreground hover:underline">Contribution Guidelines</a>
					{/if}
				</div>
			{/if}
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
		<header class="flex h-14 items-center justify-between border-b px-4 md:hidden">
			{#if activeProjectId && activeProject.data}
				{@const p = activeProject.data}
				<a href="/projects/{p.id}" class="flex min-w-0 items-center gap-2">
					{#if p.has_icon}
						<img src="{BASE_URL}/api/projects/{p.id}/icon" alt="" class="size-7 rounded-md object-cover" />
					{/if}
					<span class="truncate font-bold">{p.name}</span>
				</a>
			{:else}
				<a href="/projects" class="flex items-center gap-2">
					<img src="/icons/icon.svg" alt="" class="size-7 dark:hidden" aria-hidden="true" />
					<img src="/icons/IconDark.svg" alt="" class="size-7 hidden dark:block" aria-hidden="true" />
					<span class="font-bold">Localez</span>
				</a>
			{/if}
			<div class="flex items-center gap-3">
				{#if legalStore.hasImprint || legalStore.hasPrivacy || legalStore.hasContributions}
					<div class="flex gap-3 text-xs text-muted-foreground">
						{#if legalStore.hasImprint}
							<a href="/legal/imprint" class="hover:text-foreground hover:underline">Imprint</a>
						{/if}
						{#if legalStore.hasPrivacy}
							<a href="/legal/privacy" class="hover:text-foreground hover:underline">Privacy Policy</a>
						{/if}
						{#if legalStore.hasContributions}
							<a href="/legal/contributions" class="hover:text-foreground hover:underline">Contribution Guidelines</a>
						{/if}
					</div>
				{/if}
				<a href="https://github.com/leoklaus/localez" target="_blank" rel="noopener noreferrer" aria-label="GitHub repository" class="text-muted-foreground hover:text-foreground">
					<svg viewBox="0 0 24 24" class="size-4 fill-current" aria-hidden="true"><path d="M12 2C6.477 2 2 6.484 2 12.021c0 4.428 2.865 8.184 6.839 9.504.5.092.682-.217.682-.482 0-.237-.009-.868-.013-1.703-2.782.605-3.369-1.342-3.369-1.342-.454-1.154-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.026 2.747-1.026.546 1.378.202 2.397.1 2.65.64.7 1.028 1.595 1.028 2.688 0 3.848-2.338 4.695-4.566 4.944.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.2 22 16.447 22 12.021 22 6.484 17.523 2 12 2z"/></svg>
				</a>
			</div>
		</header>

		<!-- Mobile bottom tab bar -->
		<nav class="fixed bottom-0 left-0 right-0 z-30 border-t bg-card md:hidden">
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

		<main class="flex-1 overflow-auto pb-16 md:pb-0">
			{@render children()}
		</main>
	</div>
</div>
