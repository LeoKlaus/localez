<script lang="ts">
	import type { components } from '$lib/api/schema.d.ts';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';
	import { formatDate } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import ChevronLeft from 'lucide-svelte/icons/chevron-left';
	import ChevronRight from 'lucide-svelte/icons/chevron-right';
	import Check from 'lucide-svelte/icons/check';
	import X from 'lucide-svelte/icons/x';

	function pct(n: number, total: number) {
		return total === 0 ? 0 : Math.round((n / total) * 100);
	}

	type ProposalResponse = components['schemas']['ProposalResponse'];

	let projectId = $derived($page.params.id as string);
	let language = $derived($page.url.searchParams.get('language'));

	const LIMIT = 20;
	let offset = $state(0);

	// Reset pagination when language changes
	$effect(() => {
		language;
		offset = 0;
	});

	onMount(() => {
		if (!auth.isAdmin) goto('/projects');
	});

	const qc = useQueryClient();

	// Stats for language selection screen
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

	// Localizations in needs_review state for the selected language
	const localizations = createQuery(() => ({
		queryKey: ['review-locs', projectId, language, offset],
		enabled: !!language,
		queryFn: async () => {
			const { data, error } = await client.GET(
				'/api/projects/{project_id}/languages/{language}/localizations',
				{
					params: {
						path: { project_id: projectId, language: language! },
						query: { state: 'needs_review', offset, limit: LIMIT }
					}
				}
			);
			if (error) throw error;
			return data;
		}
	}));

	// All pending proposals for the project — joined to localizations on the client
	const proposals = createQuery(() => ({
		queryKey: ['review-proposals', projectId],
		enabled: !!language,
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/proposals', {
				params: {
					path: { project_id: projectId },
					query: { proposal_status: 'pending', limit: 500 }
				}
			});
			if (error) throw error;
			return data ?? [];
		}
	}));

	// Group proposals by localization id for O(1) lookup
	let proposalMap = $derived.by(() => {
		const map: Record<string, ProposalResponse[]> = {};
		for (const p of proposals.data ?? []) {
			(map[p.localization_id] ??= []).push(p);
		}
		return map;
	});


	function invalidate() {
		qc.invalidateQueries({ queryKey: ['review-locs', projectId, language] });
		qc.invalidateQueries({ queryKey: ['review-proposals', projectId] });
		qc.invalidateQueries({ queryKey: ['stats', projectId] });
	}

	const acceptMutation = createMutation(() => ({
		mutationFn: async ({ keyId, locId, proposalId }: { keyId: string; locId: string; proposalId: string }) => {
			const { error } = await client.POST(
				'/api/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}/accept',
				{ params: { path: { project_id: projectId, key_id: keyId, loc_id: locId, proposal_id: proposalId } } }
			);
			if (error) throw error;
		},
		onSuccess: invalidate
	}));

	const approveMutation = createMutation(() => ({
		mutationFn: async ({ keyId, locId }: { keyId: string; locId: string }) => {
			const { error } = await client.PATCH(
				'/api/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/state',
				{
					params: { path: { project_id: projectId, key_id: keyId, loc_id: locId } },
					body: { state: 'translated' }
				}
			);
			if (error) throw error;
		},
		onSuccess: invalidate
	}));

	const rejectMutation = createMutation(() => ({
		mutationFn: async ({
			keyId,
			locId,
			proposalId
		}: {
			keyId: string;
			locId: string;
			proposalId: string;
		}) => {
			const { error } = await client.DELETE(
				'/api/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals/{proposal_id}',
				{
					params: { path: { project_id: projectId, key_id: keyId, loc_id: locId, proposal_id: proposalId } }
				}
			);
			if (error) throw error;
		},
		onSuccess: invalidate
	}));

	function selectLanguage(lang: string) {
		goto(`/projects/${projectId}/review?language=${lang}`);
	}

	function clearLanguage() {
		goto(`/projects/${projectId}/review`);
	}
</script>

<div class="p-4 md:p-6">
	{#if !language}
		<!-- ── Language selection ── -->
		<h1 class="mb-1 text-2xl font-bold">Review</h1>
		<p class="mb-6 text-sm text-muted-foreground">Select a language to review pending proposals.</p>

		{#if stats.isPending}
			<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
				{#each Array(3) as _}
					<div class="h-20 animate-pulse rounded-lg bg-muted"></div>
				{/each}
			</div>
		{:else if stats.isError}
			<p class="text-destructive">Failed to load stats.</p>
		{:else}
			{@const reviewable = (stats.data?.languages ?? []).filter((l) => l.needs_review > 0)}
			{#if reviewable.length === 0}
				<div class="flex flex-col items-center gap-3 py-20 text-center text-muted-foreground">
					<Check size={40} strokeWidth={1.5} />
					<p>All caught up — no strings are pending review.</p>
				</div>
			{:else}
				<div class="mb-3 flex items-center gap-4 text-xs text-muted-foreground">
					<span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-sm bg-green-500"></span>Translated</span>
					<span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-sm bg-yellow-400"></span>Needs review</span>
					<span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-sm bg-muted-foreground/25"></span>Missing</span>
				</div>
				<div class="divide-y rounded-lg border">
					{#each reviewable as lang}
						{@const total = lang.translated + lang.needs_review + lang.missing}
						<button
							onclick={() => selectLanguage(lang.language)}
							class="flex w-full items-center gap-4 px-4 py-4 transition-colors hover:bg-muted/50 md:py-3"
						>
							<span class="w-12 font-mono text-sm font-medium">{lang.language}</span>

							<div class="flex h-2 flex-1 overflow-hidden rounded-full bg-muted-foreground/20">
								{#if total > 0}
									<div class="h-full bg-green-500 transition-all" style="width: {pct(lang.translated, total)}%"></div>
									<div class="h-full bg-yellow-400 transition-all" style="width: {pct(lang.needs_review, total)}%"></div>
								{/if}
							</div>

							<span class="hidden text-right text-xs text-muted-foreground sm:inline">{lang.needs_review} pending review</span>
							<span class="text-right text-xs text-yellow-600 dark:text-yellow-400 sm:hidden">{lang.needs_review}</span>
						</button>
					{/each}
				</div>
			{/if}
		{/if}
	{:else}
		<!-- ── Strings review list ── -->
		<div class="mb-4 flex items-center gap-2">
			<Button variant="ghost" size="icon" onclick={clearLanguage}>
				<ChevronLeft size={16} />
			</Button>
			<h1 class="text-xl font-bold">
				Review — <span class="font-mono">{language}</span>
			</h1>
		</div>

		{#if localizations.isPending}
			<div class="space-y-3">
				{#each Array(4) as _}
					<div class="h-28 animate-pulse rounded-lg bg-muted"></div>
				{/each}
			</div>
		{:else if localizations.isError}
			<p class="text-destructive">Failed to load strings.</p>
		{:else if !localizations.data?.length}
			<div class="flex flex-col items-center gap-3 py-20 text-center text-muted-foreground">
				<Check size={40} strokeWidth={1.5} />
				<p>No strings pending review for <span class="font-mono">{language}</span>.</p>
			</div>
		{:else}
			<div class="space-y-3">
				{#each localizations.data as loc}
					{@const locProposals = proposalMap[loc.id] ?? []}
					<div class="rounded-lg border bg-card p-4">
						<!-- Key header -->
						<div class="mb-3 flex flex-wrap items-start justify-between gap-2">
							<div class="flex min-w-0 flex-1 items-center gap-2">
								<a
									href="/projects/{projectId}/strings/{loc.string_key_id}"
									class="font-mono text-sm font-semibold hover:underline"
								>
									{loc.key}
								</a>
								{#if loc.variation_type !== 'none' && loc.variation_key}
									<Badge variant="outline" class="shrink-0 text-xs">
										{loc.variation_type}: {loc.variation_key}
									</Badge>
								{/if}
							</div>
							<div class="flex shrink-0 items-center gap-2">
								<span class="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">
									needs review
								</span>
								<Button
									size="sm"
									disabled={approveMutation.isPending}
									onclick={() => approveMutation.mutate({ keyId: loc.string_key_id, locId: loc.id })}
								>
									<Check size={14} class="mr-1" />
									Accept
								</Button>
							</div>
						</div>

						{#if loc.comment}
							<p class="mb-2 text-xs text-muted-foreground">
								<span class="font-medium">Comment:</span> {loc.comment}
							</p>
						{/if}

						{#if loc.source_value}
							<p class="mb-2 text-xs text-muted-foreground">
								<span class="font-medium">Source:</span>
								<span class="font-mono">{loc.source_value}</span>
							</p>
						{/if}

						{#if loc.value}
							<div class="mb-3 rounded-md bg-muted px-3 py-2 font-mono text-sm">
								{loc.value}
							</div>
						{/if}

						<!-- Proposals -->
						{#if proposals.isPending}
							<div class="h-10 animate-pulse rounded-md bg-muted"></div>
						{:else if locProposals.length === 0}
							<p class="text-xs text-muted-foreground">No pending proposals.</p>
						{:else}
							<div class="space-y-2">
								{#each locProposals as proposal (proposal.id)}
									<div class="rounded-md border bg-background p-3">
										<p class="mb-1 font-mono text-sm">{proposal.proposed_value}</p>
										<p class="mb-3 text-xs text-muted-foreground">
											Proposed {formatDate(proposal.proposed_at)}
										</p>

										<div class="flex gap-2">
											<Button
												size="sm"
												disabled={acceptMutation.isPending}
												onclick={() => acceptMutation.mutate({
													keyId: loc.string_key_id,
													locId: loc.id,
													proposalId: proposal.id
												})}
											>
												<Check size={14} class="mr-1" />
												Accept
											</Button>
											<Button
												size="sm"
												variant="destructive"
												disabled={rejectMutation.isPending}
												onclick={() => rejectMutation.mutate({
													keyId: loc.string_key_id,
													locId: loc.id,
													proposalId: proposal.id
												})}
											>
												<X size={14} class="mr-1" />
												Reject
											</Button>
										</div>
									</div>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			</div>

			<!-- Pagination -->
			{#if localizations.data.length === LIMIT || offset > 0}
				<div class="mt-4 flex items-center justify-between">
					<Button
						variant="outline"
						size="sm"
						disabled={offset === 0}
						onclick={() => (offset = Math.max(0, offset - LIMIT))}
					>
						<ChevronLeft size={14} class="mr-1" />
						Previous
					</Button>
					<span class="text-sm text-muted-foreground">
						{offset + 1}–{offset + localizations.data.length}
					</span>
					<Button
						variant="outline"
						size="sm"
						disabled={localizations.data.length < LIMIT}
						onclick={() => (offset += LIMIT)}
					>
						Next
						<ChevronRight size={14} class="ml-1" />
					</Button>
				</div>
			{/if}
		{/if}
	{/if}
</div>
