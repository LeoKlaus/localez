<script lang="ts">
	import { page } from '$app/stores';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { formatDate } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import * as Table from '$lib/components/ui/table';
	import { Badge } from '$lib/components/ui/badge';
	import Plus from 'lucide-svelte/icons/plus';
	import Trash2 from 'lucide-svelte/icons/trash-2';
	import type { components } from '$lib/api/schema.d.ts';

	type ProjectRole = components['schemas']['ProjectRole'];

	const qc = useQueryClient();
	let projectId = $derived($page.params.id as string);

	const members = createQuery(() => ({
		queryKey: ['members', projectId],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/members', {
				params: { path: { project_id: projectId }, query: { limit: 100 } }
			});
			if (error) throw error;
			return data;
		}
	}));

	const users = createQuery(() => ({
		queryKey: ['users'],
		queryFn: async () => {
			const { data, error } = await client.GET('/api/users', { params: { query: { limit: 100 } } });
			if (error) throw error;
			return data;
		}
	}));

	let addOpen = $state(false);
	let selectedUserId = $state('');
	let selectedRole = $state<ProjectRole>('translator');
	let addError = $state('');

	const addMember = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.POST('/api/projects/{project_id}/members', {
				params: { path: { project_id: projectId } },
				body: { user_id: selectedUserId, project_role: selectedRole }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['members', projectId] });
			addOpen = false;
			selectedUserId = '';
			selectedRole = 'translator';
			addError = '';
		},
		onError: () => {
			addError = 'Failed to add member.';
		}
	}));

	const updateMember = createMutation(() => ({
		mutationFn: async ({ userId, role }: { userId: string; role: ProjectRole }) => {
			const { data, error } = await client.PATCH('/api/projects/{project_id}/members/{user_id}', {
				params: { path: { project_id: projectId, user_id: userId } },
				body: { project_role: role }
			});
			if (error) throw error;
			return data;
		},
		onSuccess: () => qc.invalidateQueries({ queryKey: ['members', projectId] })
	}));

	const removeMember = createMutation(() => ({
		mutationFn: async (userId: string) => {
			const { error } = await client.DELETE('/api/projects/{project_id}/members/{user_id}', {
				params: { path: { project_id: projectId, user_id: userId } }
			});
			if (error) throw error;
		},
		onSuccess: () => qc.invalidateQueries({ queryKey: ['members', projectId] })
	}));

	const roles: ProjectRole[] = ['guest', 'translator', 'reviewer'];

	function usernameFor(userId: string) {
		return users.data?.find((u) => u.id === userId)?.username ?? userId.slice(0, 8) + '…';
	}
</script>

<div class="p-6">
	<div class="mb-6 flex items-center justify-between">
		<div>
			<a href="/projects/{projectId}" class="text-sm text-muted-foreground hover:underline">
				← Back to project
			</a>
			<h1 class="mt-1 text-2xl font-bold">Members</h1>
		</div>
		<Button onclick={() => (addOpen = true)}>
			<Plus size={16} class="mr-2" /> Add member
		</Button>
	</div>

	{#if members.isPending}
		<div class="h-32 animate-pulse rounded-lg bg-muted"></div>
	{:else if members.isError}
		<p class="text-destructive">Failed to load members.</p>
	{:else}
		<div class="rounded-lg border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>User</Table.Head>
						<Table.Head>Role</Table.Head>
						<Table.Head>Granted</Table.Head>
						<Table.Head class="w-16"></Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each members.data ?? [] as member}
						<Table.Row>
							<Table.Cell class="font-medium">{usernameFor(member.user_id)}</Table.Cell>
							<Table.Cell>
								<Select.Root
									type="single"
									value={member.project_role}
									onValueChange={(v) => {
										if (v) updateMember.mutate({ userId: member.user_id, role: v as ProjectRole });
									}}
								>
									<Select.Trigger class="w-32">
										<Badge variant="outline">{member.project_role}</Badge>
									</Select.Trigger>
									<Select.Content>
										{#each roles as role}
											<Select.Item value={role}>{role}</Select.Item>
										{/each}
									</Select.Content>
								</Select.Root>
							</Table.Cell>
							<Table.Cell class="text-muted-foreground">{formatDate(member.granted_at)}</Table.Cell>
							<Table.Cell>
								<Button
									variant="ghost"
									size="icon"
									class="text-destructive"
									onclick={() => removeMember.mutate(member.user_id)}
								>
									<Trash2 size={14} />
								</Button>
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
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
				addMember.mutate();
			}}
			class="space-y-4"
		>
			{#if addError}
				<p class="text-sm text-destructive">{addError}</p>
			{/if}
			<div class="space-y-2">
				<Label>User ID</Label>
				<Input bind:value={selectedUserId} placeholder="UUID" required />
				<p class="text-xs text-muted-foreground">
					Find user IDs in Admin → Users. Full UUID required.
				</p>
			</div>
			<div class="space-y-2">
				<Label>Role</Label>
				<Select.Root type="single" bind:value={selectedRole}>
					<Select.Trigger class="w-full">{selectedRole}</Select.Trigger>
					<Select.Content>
						{#each roles as role}
							<Select.Item value={role}>{role}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (addOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={addMember.isPending}>Add</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
