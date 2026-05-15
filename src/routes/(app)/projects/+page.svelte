<script lang="ts">
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { formatDate } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Card from '$lib/components/ui/card';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import Plus from 'lucide-svelte/icons/plus';
	import FolderOpen from 'lucide-svelte/icons/folder-open';
	import { auth } from '$lib/stores/auth.svelte';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	const qc = useQueryClient();

	const projects = createQuery(() => ({
		queryKey: ['projects'],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects', { params: { query: { limit: 100 } } });
			if (error) throw error;
			return data;
		}
	}));

	let createOpen = $state(false);
	let name = $state('');
	let sourceLanguage = $state('en');
	let createError = $state('');

	const createProject = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.POST('/api/projects', {
				body: { name, source_language: sourceLanguage }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['projects'] });
			createOpen = false;
			name = '';
			sourceLanguage = 'en';
			createError = '';
		},
		onError: () => {
			createError = 'Failed to create project.';
		}
	}));

	async function handleCreate(e: SubmitEvent) {
		e.preventDefault();
		createProject.mutate();
	}

	function projectInitial(n: string) {
		return n.trim()[0]?.toUpperCase() ?? '?';
	}
</script>

<div class="p-6">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-2xl font-bold">Projects</h1>
		{#if auth.isAdmin}
			<Button onclick={() => (createOpen = true)}>
				<Plus size={16} class="mr-2" />
				New project
			</Button>
		{/if}
	</div>

	{#if projects.isPending}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each Array(3) as _}
				<div class="h-32 animate-pulse rounded-lg bg-muted"></div>
			{/each}
		</div>
	{:else if projects.isError}
		<p class="text-destructive">Failed to load projects.</p>
	{:else if projects.data?.length === 0}
		<div class="flex flex-col items-center gap-4 py-20 text-center text-muted-foreground">
			<FolderOpen size={48} strokeWidth={1} />
			<p>No projects yet. Create your first one.</p>
		</div>
	{:else}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
			{#each projects.data ?? [] as project}
				<a href="/projects/{project.id}">
					<Card.Root class="overflow-hidden transition-shadow hover:shadow-md">
						{#if project.accent_color}
							<div class="h-1 w-full" style="background-color: {project.accent_color}"></div>
						{/if}
						<Card.Header>
							<Card.Title class="flex items-center gap-3">
								{#if project.has_icon}
									<img
										src="{BASE_URL}/api/projects/{project.id}/icon"
										alt=""
										class="size-8 rounded-md object-cover"
									/>
								{:else if project.accent_color}
									<div
										class="flex size-8 shrink-0 items-center justify-center rounded-md text-sm font-bold text-white"
										style="background-color: {project.accent_color}"
									>
										{projectInitial(project.name)}
									</div>
								{/if}
								<span class="truncate">{project.name}</span>
								<Badge variant="secondary" class="shrink-0">{project.source_language}</Badge>
							</Card.Title>
							<Card.Description>Created {formatDate(project.created_at)}</Card.Description>
						</Card.Header>
					</Card.Root>
				</a>
			{/each}
		</div>
	{/if}
</div>

<Dialog.Root bind:open={createOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>New project</Dialog.Title>
		</Dialog.Header>
		<form onsubmit={handleCreate} class="space-y-4">
			{#if createError}
				<p class="text-sm text-destructive">{createError}</p>
			{/if}
			<div class="space-y-2">
				<Label for="pname">Project name</Label>
				<Input id="pname" bind:value={name} required maxlength={255} />
			</div>
			<div class="space-y-2">
				<Label for="lang">Source language</Label>
				<Input id="lang" bind:value={sourceLanguage} placeholder="en" required maxlength={20} />
				<p class="text-xs text-muted-foreground">BCP 47 language code, e.g. en, de, ja</p>
			</div>
			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (createOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={createProject.isPending}>
					{createProject.isPending ? 'Creating…' : 'Create'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
