<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDate } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Alert from '$lib/components/ui/alert';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import { Separator } from '$lib/components/ui/separator';
	import Pencil from 'lucide-svelte/icons/pencil';
	import Trash2 from 'lucide-svelte/icons/trash-2';
	import Users from 'lucide-svelte/icons/users';
	import Download from 'lucide-svelte/icons/download';
	import Upload from 'lucide-svelte/icons/upload';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	const qc = useQueryClient();
	let projectId = $derived($page.params.id as string);

	const project = createQuery(() => ({
		queryKey: ['project', projectId],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
			return data;
		}
	}));

	const stats = createQuery(() => ({
		queryKey: ['stats', projectId],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/stats', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
			return data;
		}
	}));

	let editOpen = $state(false);
	let deleteOpen = $state(false);
	let editName = $state('');
	let editLang = $state('');

	function openEdit() {
		editName = project.data?.name ?? '';
		editLang = project.data?.source_language ?? '';
		editOpen = true;
	}

	const updateProject = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.PATCH('/api/projects/{project_id}', {
				params: { path: { project_id: projectId } },
				body: { name: editName, source_language: editLang }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['project', projectId] });
			qc.invalidateQueries({ queryKey: ['projects'] });
			editOpen = false;
		}
	}));

	const deleteProject = createMutation(() => ({
		mutationFn: async () => {
			const { error } = await client.DELETE('/api/projects/{project_id}', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['projects'] });
			goto('/projects');
		}
	}));

	async function handleExport() {
		const res = await fetch(`${BASE_URL}/api/projects/${projectId}/export`, {
			headers: { Authorization: `Bearer ${auth.accessToken}` }
		});
		if (!res.ok) return;
		const blob = await res.blob();
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `${project.data?.name ?? 'project'}.xcstrings`;
		a.click();
		URL.revokeObjectURL(url);
	}

	let importInput = $state<HTMLInputElement | undefined>(undefined);
	let importLoading = $state(false);
	let importError = $state('');
	let importSuccess = $state(false);

	async function handleImport() {
		const file = importInput?.files?.[0];
		if (!file) return;
		importError = '';
		importSuccess = false;
		importLoading = true;
		try {
			const formData = new FormData();
			formData.append('file', file);
			const res = await fetch(`${BASE_URL}/api/projects/${projectId}/import`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${auth.accessToken}` },
				body: formData
			});
			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				importError = data.detail ?? 'Import failed.';
				return;
			}
			importSuccess = true;
			qc.invalidateQueries({ queryKey: ['strings', projectId] });
			qc.invalidateQueries({ queryKey: ['stats', projectId] });
		} finally {
			importLoading = false;
			if (importInput) importInput.value = '';
		}
	}

	function pct(n: number, total: number) {
		return total === 0 ? 0 : Math.round((n / total) * 100);
	}
</script>

<div class="p-6">
	{#if project.isPending}
		<div class="h-24 animate-pulse rounded-lg bg-muted"></div>
	{:else if project.isError}
		<p class="text-destructive">Failed to load project.</p>
	{:else if project.data}
		{@const p = project.data}
		<div class="mb-6 flex flex-wrap items-start justify-between gap-4">
			<div>
				<div class="flex items-center gap-2">
					<h1 class="text-2xl font-bold">{p.name}</h1>
					<Badge variant="secondary">{p.source_language}</Badge>
				</div>
				<p class="mt-1 text-sm text-muted-foreground">Created {formatDate(p.created_at)}</p>
			</div>
			<div class="flex flex-wrap gap-2">
				<Button variant="outline" size="sm" onclick={openEdit}>
					<Pencil size={14} class="mr-1" /> Edit
				</Button>
				<Button variant="outline" size="sm" onclick={handleExport}>
					<Download size={14} class="mr-1" /> Export
				</Button>
				<Button variant="outline" size="sm" onclick={() => importInput?.click()} disabled={importLoading}>
					<Upload size={14} class="mr-1" /> {importLoading ? 'Importing…' : 'Import'}
				</Button>
				<input bind:this={importInput} type="file" accept=".xcstrings,.json" class="hidden" onchange={handleImport} />
				<a href="/projects/{p.id}/members">
					<Button variant="outline" size="sm">
						<Users size={14} class="mr-1" /> Members
					</Button>
				</a>
				<Button variant="outline" size="sm" class="text-destructive" onclick={() => (deleteOpen = true)}>
					<Trash2 size={14} class="mr-1" /> Delete
				</Button>
			</div>
		</div>

		{#if importSuccess}
			<Alert.Root class="mb-4 border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950/50 dark:text-green-400">
				<Alert.Description>File imported successfully.</Alert.Description>
			</Alert.Root>
		{/if}
		{#if importError}
			<Alert.Root class="mb-4 border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400">
				<Alert.Description>{importError}</Alert.Description>
			</Alert.Root>
		{/if}

		<Separator class="mb-6" />

		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">Languages</h2>
			{#if stats.data}
				<span class="text-sm text-muted-foreground">{stats.data.total_strings} translatable strings</span>
			{/if}
		</div>

		<div class="mb-3 flex items-center gap-4 text-xs text-muted-foreground">
			<span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-sm bg-green-500"></span>Translated</span>
			<span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-sm bg-yellow-400"></span>Needs review</span>
			<span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-sm bg-muted-foreground/25"></span>Missing</span>
		</div>

		{#if stats.isPending}
			<div class="h-32 animate-pulse rounded-lg bg-muted"></div>
		{:else if (stats.data?.languages.length ?? 0) === 0}
			<p class="text-sm text-muted-foreground">No languages configured. Import an xcstrings file to add languages.</p>
		{:else}
			<div class="divide-y rounded-lg border">
				{#each stats.data!.languages as lang}
					{@const total = lang.translated + lang.needs_review + lang.missing}
					<a
						href="/projects/{p.id}/strings?language={lang.language}"
						class="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-muted/50"
					>
						<span class="w-12 font-mono text-sm font-medium">{lang.language}</span>

						<div class="flex h-2 flex-1 overflow-hidden rounded-full bg-muted-foreground/20">
							{#if total > 0}
								<div class="h-full bg-green-500 transition-all" style="width: {pct(lang.translated, total)}%"></div>
								<div class="h-full bg-yellow-400 transition-all" style="width: {pct(lang.needs_review, total)}%"></div>
							{/if}
						</div>

						<span class="w-52 text-right text-xs text-muted-foreground">
							{pct(lang.translated, total)}% done
							· {pct(lang.needs_review, total)}% in review
							· {pct(lang.missing, total)}% missing
						</span>
					</a>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<Dialog.Root bind:open={editOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Edit project</Dialog.Title>
		</Dialog.Header>
		<form onsubmit={(e) => { e.preventDefault(); updateProject.mutate(); }} class="space-y-4">
			<div class="space-y-2">
				<Label>Name</Label>
				<Input bind:value={editName} required maxlength={255} />
			</div>
			<div class="space-y-2">
				<Label>Source language</Label>
				<Input bind:value={editLang} required maxlength={20} />
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (editOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={updateProject.isPending}>Save</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={deleteOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Delete project?</Dialog.Title>
			<Dialog.Description>
				This will permanently delete <strong>{project.data?.name}</strong> and all its strings. This cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Button variant="outline" onclick={() => (deleteOpen = false)}>Cancel</Button>
			<Button variant="destructive" onclick={() => deleteProject.mutate()} disabled={deleteProject.isPending}>
				{deleteProject.isPending ? 'Deleting…' : 'Delete project'}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
