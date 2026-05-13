<script lang="ts">
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { formatDate } from '$lib/utils';
	import * as Table from '$lib/components/ui/table';
	import * as Select from '$lib/components/ui/select';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import type { components } from '$lib/api/schema.d.ts';
	import Trash2 from 'lucide-svelte/icons/trash-2';

	type GlobalRole = components['schemas']['GlobalRole'];

	onMount(() => {
		if (!auth.isAdmin) goto('/projects');
	});

	const qc = useQueryClient();

	const users = createQuery(() => ({
		queryKey: ['users'],
		queryFn: async () => {
			const { data, error } = await client.GET('/users', { params: { query: { limit: 100 } } });
			if (error) throw error;
			return data;
		}
	}));

	const updateRole = createMutation(() => ({
		mutationFn: async ({ userId, role }: { userId: string; role: GlobalRole }) => {
			const { error } = await client.PATCH('/users/{user_id}/role', {
				params: { path: { user_id: userId } },
				body: { global_role: role }
			});
			if (error) throw error;
		},
		onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] })
	}));

	const deactivateUser = createMutation(() => ({
		mutationFn: async (userId: string) => {
			const { error } = await client.DELETE('/users/{user_id}', {
				params: { path: { user_id: userId } }
			});
			if (error) throw error;
		},
		onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] })
	}));

	const roles: GlobalRole[] = ['user', 'admin'];
</script>

<div class="p-6">
	<h1 class="mb-6 text-2xl font-bold">Users</h1>

	{#if users.isPending}
		<div class="h-64 animate-pulse rounded-lg bg-muted"></div>
	{:else if users.isError}
		<p class="text-destructive">Failed to load users.</p>
	{:else}
		<div class="rounded-lg border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head>Username</Table.Head>
						<Table.Head>Role</Table.Head>
						<Table.Head>Status</Table.Head>
						<Table.Head>Created</Table.Head>
						<Table.Head class="w-16"></Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each users.data ?? [] as user}
						<Table.Row>
							<Table.Cell class="font-medium">{user.username}</Table.Cell>
							<Table.Cell>
								<Select.Root
									type="single"
									value={user.global_role}
									onValueChange={(v) => {
										if (v && user.id !== auth.user?.id) {
											updateRole.mutate({ userId: user.id, role: v as GlobalRole });
										}
									}}
								>
									<Select.Trigger class="w-24">
										<Badge variant={user.global_role === 'admin' ? 'default' : 'secondary'}>
											{user.global_role}
										</Badge>
									</Select.Trigger>
									<Select.Content>
										{#each roles as role}
											<Select.Item value={role}>{role}</Select.Item>
										{/each}
									</Select.Content>
								</Select.Root>
							</Table.Cell>
							<Table.Cell>
								<Badge variant={user.is_active ? 'default' : 'secondary'}>
									{user.is_active ? 'Active' : 'Inactive'}
								</Badge>
							</Table.Cell>
							<Table.Cell class="text-sm text-muted-foreground">
								{formatDate(user.created_at)}
							</Table.Cell>
							<Table.Cell>
								{#if user.id !== auth.user?.id && user.is_active}
									<Button
										variant="ghost"
										size="icon"
										class="text-destructive"
										onclick={() => deactivateUser.mutate(user.id)}
									>
										<Trash2 size={14} />
									</Button>
								{/if}
							</Table.Cell>
						</Table.Row>
					{/each}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}
</div>
