<script lang="ts">
	import type { components } from '$lib/api/schema.d.ts';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { createQuery, createMutation, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';
	import { configStore } from '$lib/stores/config.svelte';
	import { formatDate } from '$lib/utils';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import ChevronLeft from 'lucide-svelte/icons/chevron-left';
	import ChevronRight from 'lucide-svelte/icons/chevron-right';
	import Check from 'lucide-svelte/icons/check';
	import X from 'lucide-svelte/icons/x';
	import Languages from 'lucide-svelte/icons/languages';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	function pct(n: number, total: number) {
		return total === 0 ? 0 : Math.round((n / total) * 100);
	}

	type ProposalResponse = components['schemas']['ProposalResponse'];

	let projectId = $derived($page.params.id as string);
	let language = $derived($page.url.searchParams.get('language'));

	const LIMIT = 20;
	let offset = $state(0);
	let filterState = $state<'needs_review' | 'translated'>('needs_review');

	// Reset pagination when language or filter changes
	$effect(() => {
		language;
		filterState;
		offset = 0;
	});

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

	// Allow global admins, project admins, and project reviewers
	let canReview = $derived(
		auth.isAdmin ||
		project.data?.my_role === 'admin' ||
		project.data?.my_role === 'reviewer'
	);

	$effect(() => {
		// Wait until project has loaded before redirecting, to avoid false negatives
		if (!project.isPending && !canReview) goto('/projects');
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
		queryKey: ['review-locs', projectId, language, filterState, offset],
		enabled: !!language,
		queryFn: async () => {
			const { data, error } = await client.GET(
				'/api/projects/{project_id}/languages/{language}/localizations',
				{
					params: {
						path: { project_id: projectId, language: language! },
						query: { state: filterState, offset, limit: LIMIT }
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
		qc.invalidateQueries({ queryKey: ['review-locs', projectId, language, filterState] });
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

	const markForReviewMutation = createMutation(() => ({
		mutationFn: async ({ keyId, locId }: { keyId: string; locId: string }) => {
			const { error } = await client.PATCH(
				'/api/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/state',
				{
					params: { path: { project_id: projectId, key_id: keyId, loc_id: locId } },
					body: { state: 'needs_review' }
				}
			);
			if (error) throw error;
		},
		onSuccess: invalidate
	}));

	const resetMutation = createMutation(() => ({
		mutationFn: async ({ keyId, locId }: { keyId: string; locId: string }) => {
			const { error } = await client.PATCH(
				'/api/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/state',
				{
					params: { path: { project_id: projectId, key_id: keyId, loc_id: locId } },
					body: { state: 'new' }
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

	// Back-translation — ephemeral, keyed by localization id or proposal id
	let backTranslations = $state<Record<string, string>>({});
	let backTranslating = $state<Record<string, boolean>>({});

	async function toggleBackTranslate(id: string, type: 'localization' | 'proposal') {
		if (backTranslations[id]) {
			const { [id]: _, ...rest } = backTranslations;
			backTranslations = rest;
			return;
		}
		backTranslating = { ...backTranslating, [id]: true };
		const path = type === 'localization'
			? `${BASE_URL}/api/projects/${projectId}/localizations/${id}/back-translate`
			: `${BASE_URL}/api/projects/${projectId}/proposals/${id}/back-translate`;
		try {
			const res = await fetch(path, {
				method: 'POST',
				headers: { Authorization: `Bearer ${auth.accessToken}` }
			});
			if (res.ok) {
				const data = await res.json();
				backTranslations = { ...backTranslations, [id]: data.text };
			}
		} finally {
			const { [id]: _, ...rest } = backTranslating;
			backTranslating = rest;
		}
	}

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
		<div class="mb-4 flex flex-wrap items-center justify-between gap-3">
			<div class="flex items-center gap-2">
				<Button variant="ghost" size="icon" onclick={clearLanguage}>
					<ChevronLeft size={16} />
				</Button>
				<h1 class="text-xl font-bold">
					Review — <span class="font-mono">{language}</span>
				</h1>
			</div>
			<div class="flex rounded-md border text-sm">
				<button
					onclick={() => (filterState = 'needs_review')}
					class="px-3 py-1.5 transition-colors {filterState === 'needs_review'
						? 'bg-primary text-primary-foreground'
						: 'text-muted-foreground hover:text-foreground'} rounded-l-md"
				>
					Needs review
				</button>
				<button
					onclick={() => (filterState = 'translated')}
					class="px-3 py-1.5 transition-colors {filterState === 'translated'
						? 'bg-primary text-primary-foreground'
						: 'text-muted-foreground hover:text-foreground'} rounded-r-md border-l"
				>
					Translated
				</button>
			</div>
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
								{#if filterState === 'needs_review'}
									<span class="rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400">needs review</span>
									<Button
										size="sm"
										disabled={approveMutation.isPending}
										onclick={() => approveMutation.mutate({ keyId: loc.string_key_id, locId: loc.id })}
									>
										<Check size={14} class="mr-1" />
										Accept
									</Button>
								{:else}
									<span class="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">translated</span>
									<Button
										size="sm"
										variant="outline"
										disabled={markForReviewMutation.isPending}
										onclick={() => markForReviewMutation.mutate({ keyId: loc.string_key_id, locId: loc.id })}
									>
										Mark for review
									</Button>
									<Button
										size="sm"
										variant="outline"
										class="text-destructive hover:text-destructive"
										disabled={resetMutation.isPending}
										onclick={() => resetMutation.mutate({ keyId: loc.string_key_id, locId: loc.id })}
									>
										<X size={14} class="mr-1" />
										Reset
									</Button>
								{/if}
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
							{#if configStore.aiEnabled}
								<div class="mb-3">
									<button
										onclick={() => toggleBackTranslate(loc.id, 'localization')}
										disabled={backTranslating[loc.id]}
										class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
									>
										<Languages size={12} />
										{backTranslations[loc.id] ? 'Hide back-translation' : backTranslating[loc.id] ? 'Translating…' : `Back-translate via ${configStore.providerLabel}`}
									</button>
									{#if backTranslations[loc.id]}
										<p class="mt-1.5 font-mono text-xs text-muted-foreground">
											→ {backTranslations[loc.id]}
										</p>
									{/if}
								</div>
							{/if}
						{/if}

						<!-- Proposals (only relevant in needs_review mode) -->
						{#if filterState === 'translated'}
							<!-- no proposals shown for translated items -->
						{:else if proposals.isPending}
							<div class="h-10 animate-pulse rounded-md bg-muted"></div>
						{:else if locProposals.length === 0 && filterState === 'needs_review'}
							<p class="text-xs text-muted-foreground">No pending proposals.</p>
						{:else}
							<div class="space-y-2">
								{#each locProposals as proposal (proposal.id)}
									<div class="rounded-md border bg-background p-3">
										<p class="mb-1 font-mono text-sm">{proposal.proposed_value}</p>
										{#if configStore.aiEnabled}
										<div class="mb-3">
											<button
												onclick={() => toggleBackTranslate(proposal.id, 'proposal')}
												disabled={backTranslating[proposal.id]}
												class="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
											>
												<Languages size={12} />
												{backTranslations[proposal.id] ? 'Hide back-translation' : backTranslating[proposal.id] ? 'Translating…' : `Back-translate via ${configStore.providerLabel}`}
											</button>
											{#if backTranslations[proposal.id]}
												<p class="mt-1.5 font-mono text-xs text-muted-foreground">
													→ {backTranslations[proposal.id]}
												</p>
											{/if}
										</div>
									{/if}
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
