<script lang="ts">
	import { page } from '$app/stores';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { formatDate } from '$lib/utils';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { Textarea } from '$lib/components/ui/textarea';
	import * as Card from '$lib/components/ui/card';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Separator } from '$lib/components/ui/separator';
	import type { components } from '$lib/api/schema.d.ts';
	import Check from 'lucide-svelte/icons/check';
	import X from 'lucide-svelte/icons/x';
	import Plus from 'lucide-svelte/icons/plus';

	type LocalizationState = components['schemas']['LocalizationState'];
	type LocalizationResponse = components['schemas']['LocalizationResponse'];

	const qc = useQueryClient();
	let projectId = $derived($page.params.id as string);
	let keyId = $derived($page.params.keyId as string);

	const stringDetail = createQuery(() => ({
		queryKey: ['string', projectId, keyId],
		queryFn: async () => {
			const { data, error } = await client.GET('/projects/{project_id}/strings/{key_id}', {
				params: { path: { project_id: projectId, key_id: keyId } }
			});
			if (error) throw error;
			return data;
		}
	}));

	const stateColors: Record<LocalizationState, string> = {
		new: 'bg-muted text-muted-foreground',
		needs_review: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
		translated: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
	};

	let proposalDialogOpen = $state(false);
	let selectedLocId = $state('');
	let proposedValue = $state('');
	let proposalError = $state('');

	const createProposal = createMutation(() => ({
		mutationFn: async () => {
			const { data, error } = await client.POST(
				'/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals',
				{
					params: { path: { project_id: projectId, key_id: keyId, loc_id: selectedLocId } },
					body: { proposed_value: proposedValue }
				}
			);
			if (error) throw error;
			return data;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['proposals', projectId, keyId, selectedLocId] });
			proposalDialogOpen = false;
			proposedValue = '';
			proposalError = '';
		},
		onError: () => {
			proposalError = 'Failed to submit proposal.';
		}
	}));

	function openProposalDialog(locId: string) {
		selectedLocId = locId;
		proposalDialogOpen = true;
	}
</script>

<div class="p-6">
	<div class="mb-4">
		<a href="/projects/{projectId}/strings" class="text-sm text-muted-foreground hover:underline">
			← Back to strings
		</a>
	</div>

	{#if stringDetail.isPending}
		<div class="h-64 animate-pulse rounded-lg bg-muted"></div>
	{:else if stringDetail.isError}
		<p class="text-destructive">Failed to load string.</p>
	{:else if stringDetail.data}
		{@const str = stringDetail.data}
		<div class="mb-6">
			<h1 class="font-mono text-xl font-bold">{str.key}</h1>
			{#if str.comment}
				<p class="mt-1 text-sm text-muted-foreground">{str.comment}</p>
			{/if}
			<div class="mt-2 flex gap-2">
				<Badge variant={str.should_translate ? 'default' : 'secondary'}>
					{str.should_translate ? 'To translate' : 'Do not translate'}
				</Badge>
			</div>
		</div>

		<Separator class="mb-6" />

		<h2 class="mb-4 text-lg font-semibold">Localizations</h2>

		{#if str.localizations.length === 0}
			<p class="text-muted-foreground">No localizations yet.</p>
		{:else}
			<div class="space-y-4">
				{#each str.localizations as loc}
					{@render localizationCard(loc)}
				{/each}
			</div>
		{/if}
	{/if}
</div>

<Dialog.Root bind:open={proposalDialogOpen}>
	<Dialog.Content class="sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>Submit translation proposal</Dialog.Title>
		</Dialog.Header>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				createProposal.mutate();
			}}
			class="space-y-4"
		>
			{#if proposalError}
				<p class="text-sm text-destructive">{proposalError}</p>
			{/if}
			<Textarea
				bind:value={proposedValue}
				placeholder="Enter your translation…"
				rows={4}
				required
			/>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (proposalDialogOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={createProposal.isPending}>Submit</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

{#snippet localizationCard(loc: LocalizationResponse)}
	{@const proposals = createQuery(() => ({
		queryKey: ['proposals', projectId, keyId, loc.id],
		queryFn: async () => {
			const { data, error } = await client.GET(
				'/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals',
				{
					params: {
						path: { project_id: projectId, key_id: keyId, loc_id: loc.id },
						query: { limit: 20 }
					}
				}
			);
			if (error) throw error;
			return data;
		}
	}))}

	{@const acceptProposal = createMutation(() => ({
		mutationFn: async (proposalId: string) => {
			const { error } = await client.POST(
				'/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}/accept',
				{
					params: {
						path: {
							project_id: projectId,
							key_id: keyId,
							loc_id: loc.id,
							proposal_id: proposalId
						}
					}
				}
			);
			if (error) throw error;
		},
		onSuccess: () => {
			qc.invalidateQueries({ queryKey: ['proposals', projectId, keyId, loc.id] });
			qc.invalidateQueries({ queryKey: ['string', projectId, keyId] });
		}
	}))}

	{@const rejectProposal = createMutation(() => ({
		mutationFn: async (proposalId: string) => {
			const { error } = await client.POST(
				'/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}/reject',
				{
					params: {
						path: {
							project_id: projectId,
							key_id: keyId,
							loc_id: loc.id,
							proposal_id: proposalId
						}
					}
				}
			);
			if (error) throw error;
		},
		onSuccess: () => qc.invalidateQueries({ queryKey: ['proposals', projectId, keyId, loc.id] })
	}))}

	<Card.Root>
		<Card.Header class="pb-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					<span class="font-semibold">{loc.language}</span>
					{#if loc.variation_type !== 'none'}
						<Badge variant="outline">{loc.variation_type}: {loc.variation_key}</Badge>
					{/if}
					<span class={`rounded-full px-2 py-0.5 text-xs font-medium ${stateColors[loc.state]}`}>
						{loc.state.replace('_', ' ')}
					</span>
				</div>
				<Button variant="outline" size="sm" onclick={() => openProposalDialog(loc.id)}>
					<Plus size={12} class="mr-1" /> Propose
				</Button>
			</div>
		</Card.Header>
		<Card.Content class="space-y-3">
			{#if loc.value}
				<div class="rounded-md border bg-muted/50 px-3 py-2 font-mono text-sm">{loc.value}</div>
			{:else}
				<p class="text-sm italic text-muted-foreground">No value yet</p>
			{/if}

			{#if proposals.data && proposals.data.length > 0}
				<div class="space-y-2">
					<p class="text-xs font-semibold uppercase text-muted-foreground">Proposals</p>
					{#each proposals.data as proposal}
						<div class="flex items-start justify-between gap-2 rounded-md border p-3 text-sm">
							<div class="flex-1">
								<p class="font-mono">{proposal.proposed_value}</p>
								<p class="mt-1 text-xs text-muted-foreground">
									{formatDate(proposal.proposed_at)}
									{#if proposal.reviewer_note}
										· {proposal.reviewer_note}
									{/if}
								</p>
							</div>
							<div class="flex items-center gap-1">
								{#if proposal.status === 'pending'}
									<Button
										variant="ghost"
										size="icon"
										class="size-7 text-green-600"
										onclick={() => acceptProposal.mutate(proposal.id)}
									>
										<Check size={14} />
									</Button>
									<Button
										variant="ghost"
										size="icon"
										class="size-7 text-destructive"
										onclick={() => rejectProposal.mutate(proposal.id)}
									>
										<X size={14} />
									</Button>
								{:else}
									<Badge variant={proposal.status === 'accepted' ? 'default' : 'secondary'}>
										{proposal.status}
									</Badge>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</Card.Content>
	</Card.Root>
{/snippet}
