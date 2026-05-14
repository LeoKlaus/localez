<script lang="ts">
	import { page } from '$app/stores';
	import { createQuery } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { Input } from '$lib/components/ui/input';
	import * as Select from '$lib/components/ui/select';
	import * as Table from '$lib/components/ui/table';
	import { Button } from '$lib/components/ui/button';
	import type { components } from '$lib/api/schema.d.ts';
	import Search from 'lucide-svelte/icons/search';
	import ChevronLeft from 'lucide-svelte/icons/chevron-left';
	import ChevronRight from 'lucide-svelte/icons/chevron-right';

	type LocalizationState = components['schemas']['LocalizationState'];

	const LIMIT = 50;
	let projectId = $derived($page.params.id as string);

	let q = $state('');
	let language = $state($page.url.searchParams.get('language') ?? '');
	let stateFilter = $state<LocalizationState | ''>('');
	let offset = $state(0);

	// When language is set, use the language localizations endpoint
	const langStrings = createQuery(() => ({
		queryKey: ['lang-strings', projectId, language, { stateFilter, offset }],
		enabled: !!language,
		queryFn: async () => {
			const { data, error, response } = await client.GET(
				'/api/projects/{project_id}/languages/{language}/localizations',
				{
					params: {
						path: { project_id: projectId, language },
						query: {
							state: (stateFilter as LocalizationState) || undefined,
							offset,
							limit: LIMIT
						}
					}
				}
			);
			if (error) throw error;
			const total = parseInt(response.headers.get('X-Total-Count') ?? '0', 10);
			return { items: data ?? [], total };
		}
	}));

	// When no language is set, use the strings list endpoint
	const strings = createQuery(() => ({
		queryKey: ['strings', projectId, { q, stateFilter, offset }],
		enabled: !language,
		queryFn: async () => {
			const { data, error, response } = await client.GET('/api/projects/{project_id}/strings', {
				params: {
					path: { project_id: projectId },
					query: {
						q: q || undefined,
						state: (stateFilter as LocalizationState) || undefined,
						offset,
						limit: LIMIT
					}
				}
			});
			if (error) throw error;
			const total = parseInt(response.headers.get('X-Total-Count') ?? '0', 10);
			return { items: data ?? [], total };
		}
	}));

	function resetPagination() {
		offset = 0;
	}

	let isPending = $derived(language ? langStrings.isPending : strings.isPending);
	let isError = $derived(language ? langStrings.isError : strings.isError);
	let total = $derived(language ? (langStrings.data?.total ?? 0) : (strings.data?.total ?? 0));
	let hasMore = $derived(offset + LIMIT < total);

	const stateColors: Record<LocalizationState, string> = {
		new: 'bg-muted text-muted-foreground',
		needs_review: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
		translated: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
	};

	const stateLabel: Record<string, string> = {
		'': 'All states',
		new: 'New',
		needs_review: 'Needs review',
		translated: 'Translated'
	};
</script>

<div class="p-6">
	<div class="mb-4">
		<a href="/projects/{projectId}" class="text-sm text-muted-foreground hover:underline">
			← Back to project
		</a>
		<h1 class="mt-1 text-2xl font-bold">
			Strings{language ? ` — ${language}` : ''}
		</h1>
	</div>

	<div class="mb-4 flex flex-wrap gap-3">
		{#if !language}
			<div class="relative min-w-40 flex-1">
				<Search size={14} class="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
				<Input class="pl-8" placeholder="Search keys…" bind:value={q} oninput={resetPagination} />
			</div>
		{/if}
		<Select.Root
			type="single"
			value={stateFilter}
			onValueChange={(v) => {
				stateFilter = (v ?? '') as LocalizationState | '';
				resetPagination();
			}}
		>
			<Select.Trigger class="w-36">{stateLabel[stateFilter] ?? 'All states'}</Select.Trigger>
			<Select.Content>
				<Select.Item value="">All states</Select.Item>
				<Select.Item value="new">New</Select.Item>
				<Select.Item value="needs_review">Needs review</Select.Item>
				<Select.Item value="translated">Translated</Select.Item>
			</Select.Content>
		</Select.Root>
	</div>

	{#if isPending}
		<div class="h-64 animate-pulse rounded-lg bg-muted"></div>
	{:else if isError}
		<p class="text-destructive">Failed to load strings.</p>
	{:else if language}
		<div class="rounded-lg border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head class="w-64">Key</Table.Head>
						<Table.Head>Translation</Table.Head>
						<Table.Head class="w-32">State</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each langStrings.data?.items ?? [] as loc}
						<Table.Row class="cursor-pointer hover:bg-muted/50">
							<Table.Cell>
								<a
									href="/projects/{projectId}/strings/{loc.string_key_id}"
									class="block font-mono text-xs font-medium hover:underline"
								>
									{loc.key}
								</a>
							</Table.Cell>
							<Table.Cell class="text-sm">
								{#if loc.value}
									<a href="/projects/{projectId}/strings/{loc.string_key_id}" class="block hover:underline">
										{loc.value}
									</a>
								{:else}
									<span class="italic text-muted-foreground">No value</span>
								{/if}
							</Table.Cell>
							<Table.Cell>
								<span class="rounded-full px-2 py-0.5 text-xs font-medium {stateColors[loc.state]}">
									{loc.state.replace('_', ' ')}
								</span>
							</Table.Cell>
						</Table.Row>
					{/each}
					{#if (langStrings.data?.items.length ?? 0) === 0}
						<Table.Row>
							<Table.Cell colspan={3} class="py-12 text-center text-muted-foreground">
								No translations found.
							</Table.Cell>
						</Table.Row>
					{/if}
				</Table.Body>
			</Table.Root>
		</div>
	{:else}
		<div class="rounded-lg border">
			<Table.Root>
				<Table.Header>
					<Table.Row>
						<Table.Head class="max-w-xs">Key</Table.Head>
						<Table.Head>Comment</Table.Head>
						<Table.Head class="w-28">Updated</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each strings.data?.items ?? [] as str}
						<Table.Row class={str.should_translate ? 'cursor-pointer hover:bg-muted/50' : 'opacity-50'}>
							<Table.Cell>
								{#if str.should_translate}
									<a
										href="/projects/{projectId}/strings/{str.id}"
										class="block font-mono text-xs font-medium hover:underline"
									>
										{str.key}
									</a>
								{:else}
									<div class="flex items-center gap-2">
										<span class="font-mono text-xs font-medium">{str.key}</span>
										<span class="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
											do not translate
										</span>
									</div>
								{/if}
							</Table.Cell>
							<Table.Cell class="max-w-xs truncate text-sm text-muted-foreground">
								{str.comment ?? '—'}
							</Table.Cell>
							<Table.Cell class="text-xs text-muted-foreground">
								{new Date(str.updated_at).toLocaleDateString()}
							</Table.Cell>
						</Table.Row>
					{/each}
					{#if (strings.data?.items.length ?? 0) === 0}
						<Table.Row>
							<Table.Cell colspan={3} class="py-12 text-center text-muted-foreground">
								No strings match your filters.
							</Table.Cell>
						</Table.Row>
					{/if}
				</Table.Body>
			</Table.Root>
		</div>
	{/if}

	<div class="mt-4 flex items-center justify-between text-sm text-muted-foreground">
		<span>
			{#if total > 0}
				Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
			{:else}
				No results
			{/if}
		</span>
		<div class="flex gap-2">
			<Button
				variant="outline"
				size="sm"
				disabled={offset === 0}
				onclick={() => (offset = Math.max(0, offset - LIMIT))}
			>
				<ChevronLeft size={14} />
			</Button>
			<Button variant="outline" size="sm" disabled={!hasMore} onclick={() => (offset += LIMIT)}>
				<ChevronRight size={14} />
			</Button>
		</div>
	</div>
</div>
