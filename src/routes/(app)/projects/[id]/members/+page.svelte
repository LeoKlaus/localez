<script lang="ts">
	import { page } from '$app/stores';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { formatDate } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Label } from '$lib/components/ui/label';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import * as Table from '$lib/components/ui/table';
	import { Badge } from '$lib/components/ui/badge';
	import Plus from 'lucide-svelte/icons/plus';
	import Trash2 from 'lucide-svelte/icons/trash-2';
	import type { components } from '$lib/api/schema.d.ts';

	type LanguageRole = components['schemas']['LanguageRole'];
	type LanguageRoleResponse = components['schemas']['LanguageRoleResponse'];

	const qc = useQueryClient();
	let projectId = $derived($page.params.id as string);

	const roles = createQuery(() => ({
		queryKey: ['language-roles', projectId],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/language-roles', {
				params: { path: { project_id: projectId } }
			});
			if (error) throw error;
			return data ?? [];
		}
	}));

	const users = createQuery(() => ({
		queryKey: ['users'],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/users', { params: { query: { limit: 200 } } });
			if (error) throw error;
			return data ?? [];
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

	let projectLanguages = $derived(
		(stats.data?.languages ?? []).map((l) => l.language).sort()
	);

	let grouped = $derived.by((): Map<string, LanguageRoleResponse[]> => {
		const map = new Map<string, LanguageRoleResponse[]>();
		for (const r of roles.data ?? []) {
			if (!map.has(r.language)) map.set(r.language, []);
			map.get(r.language)!.push(r);
		}
		return map;
	});

	let languages = $derived([...grouped.keys()].sort());

	function usernameFor(userId: string) {
		return users.data?.find((u) => u.id === userId)?.username ?? userId.slice(0, 8) + '…';
	}

	// Add dialog
	let addOpen = $state(false);
	let addUserId = $state('');
	let addLanguage = $state('');
	let addRole = $state<LanguageRole>('translator');
	let addError = $state('');

	const setRole = createMutation(() => ({
		mutationFn: async ({ userId, language, role }: { userId: string; language: string; role: LanguageRole }) => {
			const { error } = await client.PUT(
				'/api/projects/{project_id}/members/{user_id}/language-roles/{language}',
				{
					params: { path: { project_id: projectId, user_id: userId, language } },
					body: { role }
				}
			);
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['language-roles', projectId] });
			addOpen = false;
			addUserId = '';
			addLanguage = '';
			addRole = 'translator';
			addError = '';
		},
		onError: () => {
			addError = 'Failed to assign role.';
		}
	}));

	const removeRole = createMutation(() => ({
		mutationFn: async ({ userId, language }: { userId: string; language: string }) => {
			const { error } = await client.DELETE(
				'/api/projects/{project_id}/members/{user_id}/language-roles/{language}',
				{ params: { path: { project_id: projectId, user_id: userId, language } } }
			);
			if (error) throw error;
		},
		onSuccess: () => qc.invalidateQueries({ queryKey: ['language-roles', projectId] })
	}));

	const roleLabels: Record<LanguageRole, string> = { translator: 'Translator', reviewer: 'Reviewer' };
</script>

<div class="p-6">
	<div class="mb-6 flex items-center justify-between">
		<div>
			<a href="/projects/{projectId}" class="text-sm text-muted-foreground hover:underline">
				← Back to project
			</a>
			<h1 class="mt-1 text-2xl font-bold">Members</h1>
		</div>
		<Button onclick={() => { addOpen = true; addError = ''; }}>
			<Plus size={16} class="mr-2" /> Add member
		</Button>
	</div>

	{#if roles.isPending}
		<div class="h-32 animate-pulse rounded-lg bg-muted"></div>
	{:else if roles.isError}
		<p class="text-destructive">Failed to load members.</p>
	{:else if languages.length === 0}
		<p class="text-sm text-muted-foreground">No members yet. Add a member to get started.</p>
	{:else}
		<div class="space-y-6">
			{#each languages as language}
				<div>
					<h2 class="mb-2 font-mono text-sm font-semibold">{language}</h2>
					<div class="rounded-lg border">
						<Table.Root>
							<Table.Header>
								<Table.Row>
									<Table.Head>User</Table.Head>
									<Table.Head class="w-40">Role</Table.Head>
									<Table.Head class="w-44">Granted</Table.Head>
									<Table.Head class="w-12"></Table.Head>
								</Table.Row>
							</Table.Header>
							<Table.Body>
								{#each grouped.get(language) ?? [] as entry}
									<Table.Row>
										<Table.Cell class="font-medium">{usernameFor(entry.user_id)}</Table.Cell>
										<Table.Cell>
											<Select.Root
												type="single"
												value={entry.role}
												onValueChange={(v) => {
													if (v && v !== entry.role) {
														setRole.mutate({ userId: entry.user_id, language, role: v as LanguageRole });
													}
												}}
											>
												<Select.Trigger class="w-32">
													<Badge variant="outline">{roleLabels[entry.role]}</Badge>
												</Select.Trigger>
												<Select.Content>
													<Select.Item value="translator">Translator</Select.Item>
													<Select.Item value="reviewer">Reviewer</Select.Item>
												</Select.Content>
											</Select.Root>
										</Table.Cell>
										<Table.Cell class="text-sm text-muted-foreground">{formatDate(entry.granted_at)}</Table.Cell>
										<Table.Cell>
											<Button
												variant="ghost"
												size="icon"
												class="text-destructive"
												onclick={() => removeRole.mutate({ userId: entry.user_id, language })}
											>
												<Trash2 size={14} />
											</Button>
										</Table.Cell>
									</Table.Row>
								{/each}
							</Table.Body>
						</Table.Root>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<Dialog.Root bind:open={addOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Add member</Dialog.Title>
		</Dialog.Header>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				setRole.mutate({ userId: addUserId, language: addLanguage, role: addRole });
			}}
			class="space-y-4"
		>
			{#if addError}
				<p class="text-sm text-destructive">{addError}</p>
			{/if}
			<div class="space-y-2">
				<Label>User</Label>
				<Select.Root type="single" value={addUserId} onValueChange={(v) => { if (v) addUserId = v; }}>
					<Select.Trigger class="w-full">
						{addUserId ? usernameFor(addUserId) : 'Select user…'}
					</Select.Trigger>
					<Select.Content>
						{#each users.data ?? [] as user}
							<Select.Item value={user.id}>{user.username}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>
			<div class="space-y-2">
				<Label>Language</Label>
				<Select.Root type="single" value={addLanguage} onValueChange={(v) => { if (v) addLanguage = v; }}>
					<Select.Trigger class="w-full">
						{addLanguage || 'Select language…'}
					</Select.Trigger>
					<Select.Content>
						{#each projectLanguages as lang}
							<Select.Item value={lang}>{lang}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
				<p class="text-xs text-muted-foreground">Only languages already in the project are shown.</p>
			</div>
			<div class="space-y-2">
				<Label>Role</Label>
				<Select.Root type="single" value={addRole} onValueChange={(v) => { if (v) addRole = v as LanguageRole; }}>
					<Select.Trigger class="w-full">{roleLabels[addRole]}</Select.Trigger>
					<Select.Content>
						<Select.Item value="translator">Translator</Select.Item>
						<Select.Item value="reviewer">Reviewer</Select.Item>
					</Select.Content>
				</Select.Root>
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (addOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={!addUserId || !addLanguage || setRole.isPending}>
					{setRole.isPending ? 'Adding…' : 'Add'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
