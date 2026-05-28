<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { prefillStore } from '$lib/stores/prefill.svelte';
	import { client } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDate, languageName, COMMON_LANGUAGE_CODES } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Alert from '$lib/components/ui/alert';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Badge } from '$lib/components/ui/badge';
	import { Separator } from '$lib/components/ui/separator';
	import Pencil from 'lucide-svelte/icons/pencil';
	import Trash2 from 'lucide-svelte/icons/trash-2';
	import Plus from 'lucide-svelte/icons/plus';
	import Download from 'lucide-svelte/icons/download';
	import Upload from 'lucide-svelte/icons/upload';
	import ClipboardCheck from 'lucide-svelte/icons/clipboard-check';
	import Key from 'lucide-svelte/icons/key';
	import Copy from 'lucide-svelte/icons/copy';
	import Globe from 'lucide-svelte/icons/globe';
	import Lock from 'lucide-svelte/icons/lock';
	import { toast } from 'svelte-sonner';

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

	// Edit project
	let editOpen = $state(false);
	let editName = $state('');
	let editLang = $state('');
	let editIsPublic = $state(false);

	function openEdit() {
		editName = project.data?.name ?? '';
		editLang = project.data?.source_language ?? '';
		editIsPublic = project.data?.is_public ?? false;
		editOpen = true;
	}

	const updateProject = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.PATCH('/api/projects/{project_id}', {
				params: { path: { project_id: projectId } },
				body: { name: editName, source_language: editLang, is_public: editIsPublic }
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

	// Icon upload / delete
	let iconInput = $state<HTMLInputElement | undefined>(undefined);
	let iconLoading = $state(false);
	let iconError = $state('');

	async function handleIconUpload() {
		const file = iconInput?.files?.[0];
		if (!file) return;
		iconError = '';
		iconLoading = true;
		try {
			const formData = new FormData();
			formData.append('file', file);
			const res = await fetch(`${BASE_URL}/api/projects/${projectId}/icon`, {
				method: 'PUT',
				headers: { Authorization: `Bearer ${auth.accessToken}` },
				body: formData
			});
			if (!res.ok) { iconError = 'Icon upload failed.'; return; }
			qc.invalidateQueries({ queryKey: ['project', projectId] });
			qc.invalidateQueries({ queryKey: ['projects'] });
		} finally {
			iconLoading = false;
			if (iconInput) iconInput.value = '';
		}
	}

	const deleteIcon = createMutation(() => ({
		mutationFn: async () => {
			const { error } = await client.DELETE('/api/projects/{project_id}/icon', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['project', projectId] });
			qc.invalidateQueries({ queryKey: ['projects'] });
		}
	}));

	// Delete project
	let deleteOpen = $state(false);

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

	// Add language
	let addLangOpen = $state(false);
	let newLanguage = $state('');
	let addLangError = $state('');

	function watchPrefill(language: string) {
		prefillStore.watch(projectId, language, BASE_URL, auth.accessToken, () => {
			qc.invalidateQueries({ queryKey: ['lang-strings', projectId] });
		});
	}

	onMount(() => {
		for (const lang of prefillStore.pendingLanguages(projectId)) {
			watchPrefill(lang);
		}
	});

	const addLanguage = createMutation(() => ({
		mutationFn: async () => {
			const { error } = await client.POST('/api/projects/{project_id}/languages', {
				params: { path: { project_id: projectId } },
				body: { language: newLanguage.trim() }
			});
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['project', projectId] });
			qc.invalidateQueries({ queryKey: ['stats', projectId] });
			const lang = newLanguage.trim();
			addLangOpen = false;
			newLanguage = '';
			addLangError = '';
			watchPrefill(lang);
		},
		onError: () => {
			addLangError = 'Failed to add language.';
		}
	}));

	// Delete language
	const deleteLanguage = createMutation(() => ({
		mutationFn: async (language: string) => {
			const { error } = await client.DELETE('/api/projects/{project_id}/languages/{language}', {
				params: { path: { project_id: projectId, language } }
			});
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['project', projectId] });
			qc.invalidateQueries({ queryKey: ['stats', projectId] });
		}
	}));

	// Export
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

	// Import
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
			qc.invalidateQueries({ queryKey: ['project', projectId] });
		} finally {
			importLoading = false;
			if (importInput) importInput.value = '';
		}
	}

	function pct(n: number, total: number) {
		return total === 0 ? 0 : Math.round((n / total) * 100);
	}

	// Derive the current user's project role from the project response (my_role is populated by get_project)
	let myProjectRole = $derived(project.data?.my_role ?? null);
	// project admin: global admin OR member with admin role
	let isProjectAdmin = $derived(auth.isAdmin || myProjectRole === 'admin');
	// project reviewer: project admin OR member with reviewer role
	let isProjectReviewer = $derived(isProjectAdmin || myProjectRole === 'reviewer');
	// project member: global admin OR any member (any role)
	let isProjectMember = $derived(auth.isAdmin || myProjectRole !== null);

	// API tokens (project admin and above)
	const tokens = createQuery(() => ({
		queryKey: ['tokens', projectId],
		enabled: isProjectAdmin,
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/tokens', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
			return data;
		}
	}));

	let createTokenOpen = $state(false);
	let newTokenName = $state('');
	let newTokenType = $state<'import_token' | 'export_token'>('import_token');
	let createdToken = $state<{ name: string; token: string; token_type: 'import_token' | 'export_token' } | null>(null);
	let createdTokenOpen = $state(false);

	const createToken = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.POST('/api/projects/{project_id}/tokens', {
				params: { path: { project_id: projectId } },
				body: { name: newTokenName.trim(), token_type: newTokenType }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: (data) => {
			qc.invalidateQueries({ queryKey: ['tokens', projectId] });
			createTokenOpen = false;
			createdToken = { name: data!.name, token: data!.token, token_type: data!.token_type };
			createdTokenOpen = true;
			newTokenName = '';
			newTokenType = 'import_token';
		}
	}));

	const revokeToken = createMutation(() => ({
		mutationFn: async (tokenId: string) => {
			const { error } = await client.DELETE('/api/projects/{project_id}/tokens/{token_id}', {
				params: { path: { project_id: projectId, token_id: tokenId } }
			});
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['tokens', projectId] });
		}
	}));

	async function copyToken(token: string) {
		await navigator.clipboard.writeText(token);
		toast.success('Token copied to clipboard');
	}

	// Members (project admin and above only)
	const members = createQuery(() => ({
		queryKey: ['members', projectId],
		enabled: isProjectAdmin,
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/members', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
			return data;
		}
	}));

	let addMemberOpen = $state(false);
	let newMemberUsername = $state('');
	let addMemberError = $state('');

	const addMember = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.POST('/api/projects/{project_id}/members', {
				params: { path: { project_id: projectId } },
				body: { username: newMemberUsername.trim() }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['members', projectId] });
			addMemberOpen = false;
			newMemberUsername = '';
			addMemberError = '';
		},
		onError: (err: unknown) => {
			const code = (err as { detail?: { code?: string } })?.detail?.code;
			if (code === 'USER_NOT_FOUND') addMemberError = 'User not found.';
			else if (code === 'ALREADY_MEMBER') addMemberError = 'User is already a member.';
			else addMemberError = 'Failed to add member.';
		}
	}));

	const updateMemberRole = createMutation(() => ({
		mutationFn: async ({ memberId, role }: { memberId: string; role: string }) => {
			const { data, error } = await client.PATCH('/api/projects/{project_id}/members/{member_id}', {
				params: { path: { project_id: projectId, member_id: memberId } },
				body: { role: role as 'admin' | 'reviewer' | 'translator' }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['members', projectId] });
		}
	}));

	const removeMember = createMutation(() => ({
		mutationFn: async (memberId: string) => {
			const { error } = await client.DELETE('/api/projects/{project_id}/members/{member_id}', {
				params: { path: { project_id: projectId, member_id: memberId } }
			});
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['members', projectId] });
		}
	}));
</script>

<div class="p-6">
	{#if project.isPending}
		<div class="h-24 animate-pulse rounded-lg bg-muted"></div>
	{:else if project.isError}
		<p class="text-destructive">Failed to load project.</p>
	{:else if project.data}
		{@const p = project.data}
		<div class="mb-6 flex flex-wrap items-start justify-between gap-4">
			<div class="flex items-center gap-4">
				{#if p.has_icon}
					<img src="{BASE_URL}/api/projects/{p.id}/icon" alt="" class="size-16 rounded-xl object-cover shadow-sm" />
				{/if}
				<div>
					<div class="flex items-center gap-2 flex-wrap">
						<h1 class="text-2xl font-bold">{p.name}</h1>
						<Badge variant="secondary">{languageName(p.source_language)}</Badge>
						{#if p.is_public}
							<Badge variant="outline" class="gap-1 text-muted-foreground">
								<Globe size={11} />Public
							</Badge>
						{:else}
							<Badge variant="outline" class="gap-1 text-muted-foreground">
								<Lock size={11} />Private
							</Badge>
						{/if}
					</div>
					<p class="mt-1 text-sm text-muted-foreground">Created {formatDate(p.created_at)}</p>
				</div>
			</div>
			{#if isProjectReviewer}
				<div class="flex flex-wrap gap-2">
					<Button variant="outline" size="sm" href="/projects/{p.id}/review">
						<ClipboardCheck size={14} class="mr-1" /> Review
					</Button>
					{#if isProjectAdmin}
						<Button variant="outline" size="sm" onclick={openEdit}>
							<Pencil size={14} class="mr-1" /> Edit
						</Button>
						<Button variant="outline" size="sm" onclick={() => iconInput?.click()} disabled={iconLoading}>
							<Upload size={14} class="mr-1" /> {iconLoading ? 'Uploading…' : p.has_icon ? 'Replace icon' : 'Upload icon'}
						</Button>
						<input bind:this={iconInput} type="file" accept="image/*" class="hidden" onchange={handleIconUpload} />
						{#if p.has_icon}
							<Button variant="outline" size="sm" onclick={() => deleteIcon.mutate()} disabled={deleteIcon.isPending}>
								<Trash2 size={14} class="mr-1" /> Remove icon
							</Button>
						{/if}
						<Button variant="outline" size="sm" onclick={handleExport}>
							<Download size={14} class="mr-1" /> Export
						</Button>
						<Button variant="outline" size="sm" onclick={() => importInput?.click()} disabled={importLoading}>
							<Upload size={14} class="mr-1" /> {importLoading ? 'Importing…' : 'Import'}
						</Button>
						<input bind:this={importInput} type="file" accept=".xcstrings,.json" class="hidden" onchange={handleImport} />
						<Button variant="outline" size="sm" class="text-destructive" onclick={() => (deleteOpen = true)}>
							<Trash2 size={14} class="mr-1" /> Delete
						</Button>
					{/if}
				</div>
			{/if}
		</div>
		{#if iconError}
			<Alert.Root class="mb-4 border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400">
				<Alert.Description>{iconError}</Alert.Description>
			</Alert.Root>
		{/if}

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

		{#each stats.data?.languages ?? [] as lang}
			{@const prefill = prefillStore.get(projectId, lang.language)}
			{#if prefill}
				<Alert.Root class="mb-2 border-violet-200 bg-violet-50 text-violet-800 dark:border-violet-800 dark:bg-violet-950/50 dark:text-violet-300">
					<Alert.Description class="flex items-center gap-2">
						{#if prefill.running}
							<span class="inline-block size-3 animate-spin rounded-full border-2 border-violet-400 border-t-transparent"></span>
						{:else}
							✦
						{/if}
						{prefill.message}
					</Alert.Description>
				</Alert.Root>
			{/if}
		{/each}

		<div class="mb-4 flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold">Languages</h2>
				{#if stats.data}
					<p class="text-sm text-muted-foreground">{stats.data.total_strings} translatable strings</p>
				{/if}
			</div>
			{#if isProjectMember}
				<Button size="sm" onclick={() => { addLangOpen = true; newLanguage = ''; addLangError = ''; }}>
					<Plus size={14} class="mr-1" /> Add language
				</Button>
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
			<p class="text-sm text-muted-foreground">No languages configured. {auth.isAuthenticated ? 'Add a language or import an xcstrings file.' : 'Sign in to add languages.'}</p>
		{:else}
			<div class="divide-y rounded-lg border">
				{#each stats.data!.languages as lang}
					{@const total = lang.translated + lang.needs_review + lang.missing}
					<div class="flex items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/50 md:py-3">
						<a
							href="/projects/{p.id}/strings?language={lang.language}"
							class="flex flex-1 items-center gap-4"
						>
							<span class="w-36 shrink-0 truncate text-sm font-medium">{languageName(lang.language)}</span>

							<div class="flex h-2 flex-1 overflow-hidden rounded-full bg-muted-foreground/20">
								{#if total > 0}
									<div class="h-full bg-green-500 transition-all" style="width: {pct(lang.translated, total)}%"></div>
									<div class="h-full bg-yellow-400 transition-all" style="width: {pct(lang.needs_review, total)}%"></div>
								{/if}
							</div>

							<span class="hidden text-right text-xs text-muted-foreground sm:inline">{pct(lang.translated, total)}% done · {pct(lang.needs_review, total)}% in review · {pct(lang.missing, total)}% missing</span>
							<span class="text-right text-xs text-muted-foreground sm:hidden">{pct(lang.translated, total)}%</span>
						</a>
						{#if isProjectAdmin}
							<Button
								variant="ghost"
								size="icon"
								class="size-9 shrink-0 text-muted-foreground hover:text-destructive md:size-7"
								onclick={() => deleteLanguage.mutate(lang.language)}
							>
								<Trash2 size={16} class="md:hidden" />
								<Trash2 size={14} class="hidden md:block" />
							</Button>
						{/if}
					</div>
				{/each}
			</div>
		{/if}

		{#if isProjectAdmin}
			<Separator class="my-6" />

			<div class="mb-4 flex items-center justify-between">
				<div>
					<h2 class="text-lg font-semibold">Members</h2>
					<p class="text-sm text-muted-foreground">Users with explicit access to this project.</p>
				</div>
				<Button size="sm" onclick={() => { addMemberOpen = true; newMemberUsername = ''; addMemberError = ''; }}>
					<Plus size={14} class="mr-1" /> Add member
				</Button>
			</div>

			{#if members.isPending}
				<div class="h-16 animate-pulse rounded-lg bg-muted"></div>
			{:else if (members.data?.length ?? 0) === 0}
				<p class="text-sm text-muted-foreground">No members yet.</p>
			{:else}
				<div class="divide-y rounded-lg border">
					{#each members.data! as member}
						{@const isSelf = member.user_id === auth.user?.id}
						<div class="flex items-center gap-3 px-4 py-3">
							<div class="flex-1 min-w-0">
								<p class="text-sm font-medium">{member.username}</p>
								<p class="text-xs text-muted-foreground">Added {formatDate(member.created_at)}</p>
							</div>
							<select
								class="rounded-md border border-input bg-background px-2 py-1 text-xs ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
								value={member.role}
								disabled={isSelf}
								onchange={(e) => updateMemberRole.mutate({ memberId: member.id, role: e.currentTarget.value })}
							>
								<option value="translator">Translator</option>
								<option value="reviewer">Reviewer</option>
								<option value="admin">Admin</option>
							</select>
							<Button
								variant="ghost"
								size="icon"
								class="size-7 shrink-0 text-muted-foreground hover:text-destructive"
								onclick={() => removeMember.mutate(member.id)}
								disabled={isSelf || removeMember.isPending}
							>
								<Trash2 size={14} />
							</Button>
						</div>
					{/each}
				</div>
			{/if}

			<Separator class="my-6" />

			<div class="mb-4 flex items-center justify-between">
				<div>
					<h2 class="text-lg font-semibold">API Tokens</h2>
					<p class="text-sm text-muted-foreground">Tokens for CI/CD pipelines and Xcode integrations.</p>
				</div>
				<Button size="sm" onclick={() => { createTokenOpen = true; newTokenName = ''; newTokenType = 'import_token'; }}>
					<Key size={14} class="mr-1" /> Create token
				</Button>
			</div>

			{#if tokens.isPending}
				<div class="h-16 animate-pulse rounded-lg bg-muted"></div>
			{:else if (tokens.data?.length ?? 0) === 0}
				<p class="text-sm text-muted-foreground">No API tokens yet.</p>
			{:else}
				<div class="divide-y rounded-lg border">
					{#each tokens.data! as token}
						<div class="flex items-center gap-4 px-4 py-3">
							<Key size={14} class="shrink-0 text-muted-foreground" />
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2">
									<p class="text-sm font-medium truncate">{token.name}</p>
									<Badge variant={token.token_type === 'export_token' ? 'secondary' : 'outline'} class="shrink-0 text-xs">
										{token.token_type === 'export_token' ? 'export' : 'import'}
									</Badge>
								</div>
								<p class="text-xs text-muted-foreground">
									Created {formatDate(token.created_at)}
									{#if token.last_used_at}
										· Last used {formatDate(token.last_used_at)}
									{:else}
										· Never used
									{/if}
								</p>
							</div>
							<Button
								variant="ghost"
								size="sm"
								class="text-muted-foreground hover:text-destructive"
								onclick={() => revokeToken.mutate(token.id)}
								disabled={revokeToken.isPending}
							>
								<Trash2 size={14} class="mr-1" /> Revoke
							</Button>
						</div>
					{/each}
				</div>
			{/if}
		{/if}
	{/if}
</div>

<!-- Edit project dialog -->
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
				<input
					list="edit-project-languages"
					bind:value={editLang}
					required
					maxlength={20}
					class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
				/>
				<datalist id="edit-project-languages">
					{#each COMMON_LANGUAGE_CODES as code}
						<option value={code}>{languageName(code)}</option>
					{/each}
				</datalist>
				{#if editLang.trim()}
					<p class="text-xs text-muted-foreground">→ {languageName(editLang.trim())}</p>
				{/if}
			</div>
			<label class="flex items-center gap-3 cursor-pointer select-none">
				<input type="checkbox" bind:checked={editIsPublic} class="size-4 rounded border accent-primary" />
				<div>
					<span class="text-sm font-medium">Public project</span>
					<p class="text-xs text-muted-foreground">Anyone can read; authenticated users can translate</p>
				</div>
			</label>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (editOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={updateProject.isPending}>Save</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<!-- Delete project dialog -->
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

<!-- Create token dialog -->
<Dialog.Root bind:open={createTokenOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Create API token</Dialog.Title>
			<Dialog.Description>Give this token a descriptive name, e.g. the tool or pipeline that will use it.</Dialog.Description>
		</Dialog.Header>
		<form onsubmit={(e) => { e.preventDefault(); createToken.mutate(); }} class="space-y-4">
			<div class="space-y-2">
				<Label>Token name</Label>
				<Input bind:value={newTokenName} placeholder="Xcode / GitHub Actions" required maxlength={100} />
			</div>
			<div class="space-y-2">
				<Label>Type</Label>
				<div class="grid grid-cols-2 gap-2">
					<button
						type="button"
						onclick={() => (newTokenType = 'import_token')}
						class="rounded-md border px-3 py-2 text-left text-sm transition-colors {newTokenType === 'import_token' ? 'border-primary bg-primary/5 font-medium' : 'border-border hover:bg-muted'}"
					>
						<span class="font-medium">Import</span>
						<p class="mt-0.5 text-xs text-muted-foreground">Push xcstrings to this project</p>
					</button>
					<button
						type="button"
						onclick={() => (newTokenType = 'export_token')}
						class="rounded-md border px-3 py-2 text-left text-sm transition-colors {newTokenType === 'export_token' ? 'border-primary bg-primary/5 font-medium' : 'border-border hover:bg-muted'}"
					>
						<span class="font-medium">Export</span>
						<p class="mt-0.5 text-xs text-muted-foreground">Pull xcstrings from this project</p>
					</button>
				</div>
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (createTokenOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={!newTokenName.trim() || createToken.isPending}>
					{createToken.isPending ? 'Creating…' : 'Create'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<!-- Token created — show raw token once -->
<Dialog.Root bind:open={createdTokenOpen}>
	<Dialog.Content class="sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>Token created</Dialog.Title>
			<Dialog.Description>
				Copy this token now — it won't be shown again.
			</Dialog.Description>
		</Dialog.Header>
		{#if createdToken}
			<div class="space-y-3">
				<div class="flex items-center gap-2">
					<p class="text-sm font-medium">{createdToken.name}</p>
					<Badge variant={createdToken.token_type === 'export_token' ? 'secondary' : 'outline'} class="text-xs">
						{createdToken.token_type === 'export_token' ? 'export' : 'import'}
					</Badge>
				</div>
				<div class="flex items-center gap-2 rounded-md border bg-muted px-3 py-2">
					<code class="flex-1 break-all text-xs">{createdToken.token}</code>
					<Button variant="ghost" size="icon" class="size-7 shrink-0" onclick={() => copyToken(createdToken!.token)}>
						<Copy size={14} />
					</Button>
				</div>
				{#if createdToken.token_type === 'export_token'}
					<p class="text-xs text-muted-foreground">
						Use this token to pull translations: <code class="rounded bg-muted px-1">GET /api/projects/…/export</code> with <code class="rounded bg-muted px-1">Authorization: Bearer &lt;token&gt;</code>.
					</p>
				{:else}
					<p class="text-xs text-muted-foreground">
						Use this token to push translations: <code class="rounded bg-muted px-1">POST /api/projects/…/import</code> with <code class="rounded bg-muted px-1">Authorization: Bearer &lt;token&gt;</code>.
					</p>
				{/if}
			</div>
		{/if}
		<Dialog.Footer>
			<Button onclick={() => (createdTokenOpen = false)}>Done</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<!-- Add member dialog -->
<Dialog.Root bind:open={addMemberOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Add member</Dialog.Title>
			<Dialog.Description>Enter the username of the user to add to this project.</Dialog.Description>
		</Dialog.Header>
		<form onsubmit={(e) => { e.preventDefault(); addMember.mutate(); }} class="space-y-4">
			{#if addMemberError}
				<p class="text-sm text-destructive">{addMemberError}</p>
			{/if}
			<div class="space-y-2">
				<Label>Username</Label>
				<Input bind:value={newMemberUsername} placeholder="username" required maxlength={150} />
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (addMemberOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={!newMemberUsername.trim() || addMember.isPending}>
					{addMember.isPending ? 'Adding…' : 'Add'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<!-- Add language dialog -->
<Dialog.Root bind:open={addLangOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Add language</Dialog.Title>
		</Dialog.Header>
		<form onsubmit={(e) => { e.preventDefault(); addLanguage.mutate(); }} class="space-y-4">
			{#if addLangError}
				<p class="text-sm text-destructive">{addLangError}</p>
			{/if}
			<div class="space-y-2">
				<Label>Language</Label>
				<input
					list="add-language-suggestions"
					bind:value={newLanguage}
					placeholder="de"
					required
					maxlength={20}
					class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-xs transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
				/>
				<datalist id="add-language-suggestions">
					{#each COMMON_LANGUAGE_CODES as code}
						<option value={code}>{languageName(code)}</option>
					{/each}
				</datalist>
				{#if newLanguage.trim()}
					<p class="text-xs text-muted-foreground">→ {languageName(newLanguage.trim())}</p>
				{/if}
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (addLangOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={!newLanguage.trim() || addLanguage.isPending}>
					{addLanguage.isPending ? 'Adding…' : 'Add'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
