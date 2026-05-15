<script lang="ts">
	import { page } from '$app/stores';
	import { createQuery, useQueryClient } from '@tanstack/svelte-query';
	import { client } from '$lib/api/client';
	import { auth } from '$lib/stores/auth.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Badge } from '$lib/components/ui/badge';
	import * as Select from '$lib/components/ui/select';
	import * as Table from '$lib/components/ui/table';
	import { Button } from '$lib/components/ui/button';
	import type { components } from '$lib/api/schema.d.ts';
	import Search from 'lucide-svelte/icons/search';
	import ChevronLeft from 'lucide-svelte/icons/chevron-left';
	import ChevronRight from 'lucide-svelte/icons/chevron-right';

	type LocalizationState = components['schemas']['LocalizationState'];
	type LocalizationWithKey = components['schemas']['LocalizationWithKeyResponse'];
	type ProposalResponse = components['schemas']['ProposalResponse'];

	const qc = useQueryClient();
	const LIMIT = 50;
	let projectId = $derived($page.params.id as string);

	let q = $state('');
	let language = $state($page.url.searchParams.get('language') ?? '');
	let stateFilter = $state<LocalizationState | ''>('');
	let offset = $state(0);

	const langStrings = createQuery(() => ({
		queryKey: ['lang-strings', projectId, language, { stateFilter, offset }],
		enabled: !!language,
		queryFn: async () => {
			const { data, error, response } = await client.GET(
				'/api/projects/{project_id}/languages/{language}/localizations',
				{
					params: {
						path: { project_id: projectId, language },
						query: { state: (stateFilter as LocalizationState) || undefined, offset, limit: LIMIT }
					}
				}
			);
			if (error) throw error;
			const total = parseInt(response.headers.get('X-Total-Count') ?? '0', 10);
			return { items: data ?? [], total };
		}
	}));

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

	const pendingProposals = createQuery(() => ({
		queryKey: ['proposals-pending', projectId],
		enabled: !!language,
		queryFn: async () => {
			const { data, error } = await client.GET('/api/projects/{project_id}/proposals', {
				params: { path: { project_id: projectId }, query: { proposal_status: 'pending', limit: 1000 } }
			});
			if (error) throw error;
			return data ?? [];
		}
	}));

	function resetPagination() { offset = 0; }

	let isPending = $derived(language ? langStrings.isPending : strings.isPending);
	let isError = $derived(language ? langStrings.isError : strings.isError);
	let total = $derived(language ? (langStrings.data?.total ?? 0) : (strings.data?.total ?? 0));
	let hasMore = $derived(offset + LIMIT < total);

	type Group = { string_key_id: string; key: string; entries: LocalizationWithKey[] };

	let grouped = $derived.by((): Group[] => {
		const map = new Map<string, Group>();
		for (const loc of langStrings.data?.items ?? []) {
			if (!map.has(loc.string_key_id)) {
				map.set(loc.string_key_id, { string_key_id: loc.string_key_id, key: loc.key, entries: [] });
			}
			map.get(loc.string_key_id)!.entries.push(loc);
		}
		return [...map.values()];
	});

	let proposalsByLocId = $derived.by((): Map<string, ProposalResponse[]> => {
		const map = new Map<string, ProposalResponse[]>();
		for (const p of pendingProposals.data ?? []) {
			if (!map.has(p.localization_id)) map.set(p.localization_id, []);
			map.get(p.localization_id)!.push(p);
		}
		return map;
	});

	let drafts = $state<Record<string, string>>({});
	let submitting = $state<Record<string, boolean>>({});
	let submitError = $state<Record<string, string>>({});

	$effect(() => {
		for (const loc of langStrings.data?.items ?? []) {
			if (!(loc.id in drafts)) drafts[loc.id] = loc.value ?? '';
		}
	});

	async function submitProposal(loc: LocalizationWithKey) {
		const draft = drafts[loc.id] ?? '';
		if (draft === (loc.value ?? '') || !draft.trim()) return;
		submitting[loc.id] = true;
		submitError[loc.id] = '';
		try {
			const { error } = await client.POST(
				'/api/projects/{project_id}/strings/{key_id}/localizations/{loc_id}/proposals',
				{
					params: { path: { project_id: projectId, key_id: loc.string_key_id, loc_id: loc.id } },
					body: { proposed_value: draft }
				}
			);
			if (error) throw error;
			qc.invalidateQueries({ queryKey: ['lang-strings', projectId] });
			qc.invalidateQueries({ queryKey: ['proposals-pending', projectId] });
		} catch {
			submitError[loc.id] = 'Failed to submit.';
			drafts[loc.id] = loc.value ?? '';
		} finally {
			submitting[loc.id] = false;
		}
	}

	// Placeholder parsing
	const PLACEHOLDER_RE = /%(?:\d+\$)?(?:@|lld|ld|d|f|s)/;

	type Segment = { type: 'text' | 'placeholder'; value: string };

	function parseSegments(text: string): Segment[] {
		const parts = text.split(new RegExp(`(${PLACEHOLDER_RE.source})`));
		return parts
			.map((value, i) => ({ type: (i % 2 === 1 ? 'placeholder' : 'text') as Segment['type'], value }))
			.filter((s) => s.value !== '');
	}

	function extractPlaceholders(text: string): string[] {
		return [...new Set(text.match(new RegExp(PLACEHOLDER_RE.source, 'g')) ?? [])];
	}

	function placeholderLabel(ph: string): string {
		if (ph.endsWith('@') || ph.endsWith('s')) return 'string';
		if (ph.endsWith('f')) return 'decimal';
		return 'number';
	}

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

<!-- Shared translation input: mirror overlay + textarea + placeholder chips + proposals -->
{#snippet translationInput(loc: LocalizationWithKey, bordered = false)}
	{@const placeholders = extractPlaceholders(loc.key)}
	{#if auth.isAuthenticated}
		<div class="relative {bordered ? 'rounded-md border' : ''}">
			<div
				aria-hidden="true"
				class="pointer-events-none whitespace-pre-wrap break-words px-1 py-0.5 text-sm"
			>{#each parseSegments(drafts[loc.id] ?? '') as seg}{#if seg.type === 'placeholder'}<mark class="rounded bg-blue-100 not-italic text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">{seg.value}</mark>{:else}{seg.value}{/if}{/each}<br /></div>
			<textarea
				class="absolute inset-0 w-full rounded bg-transparent px-1 py-0.5 text-sm text-transparent outline-none ring-inset transition-shadow placeholder:italic placeholder:text-muted-foreground focus:ring-1 focus:ring-ring disabled:opacity-50 {submitError[loc.id] ? 'ring-1 ring-destructive' : ''}"
				style="resize: none; caret-color: hsl(var(--foreground))"
				placeholder="Enter translation…"
				disabled={submitting[loc.id]}
				value={drafts[loc.id] ?? ''}
				oninput={(e) => { drafts[loc.id] = e.currentTarget.value; }}
				onblur={() => submitProposal(loc)}
				onkeydown={(e) => {
					if (e.key === 'Escape') { drafts[loc.id] = loc.value ?? ''; e.currentTarget.blur(); return; }
					if (e.key === 'Enter') {
						if (e.shiftKey || e.altKey) {
							e.preventDefault();
							const el = e.currentTarget;
							const start = el.selectionStart ?? 0;
							const end = el.selectionEnd ?? 0;
							const val = drafts[loc.id] ?? '';
							drafts[loc.id] = val.slice(0, start) + '\n' + val.slice(end);
							// restore cursor after Svelte re-renders
							requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = start + 1; });
						} else {
							e.preventDefault();
							e.currentTarget.blur();
						}
					}
				}}
			></textarea>
		</div>
	{:else}
		<span class="whitespace-pre-wrap break-words px-1 py-0.5 text-sm text-muted-foreground italic">{loc.value ?? '—'}</span>
	{/if}
	{#if placeholders.length > 0}
		<div class="mt-1 flex flex-wrap items-center gap-1 pl-1">
			<span class="text-xs text-muted-foreground">Placeholders:</span>
			{#each placeholders as ph}
				<span class="flex items-center gap-0.5">
					<button
						type="button"
						class="inline rounded bg-blue-100 px-1 font-mono text-xs text-blue-700 hover:bg-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:hover:bg-blue-900/70"
						onmousedown={(e) => { e.preventDefault(); drafts[loc.id] = (drafts[loc.id] ?? '') + ph; }}
						title="Click to insert into translation"
					>{ph}</button>
					<span class="text-xs text-muted-foreground">{placeholderLabel(ph)}</span>
				</span>
			{/each}
		</div>
	{/if}
	{#if auth.isAuthenticated}
		{#each proposalsByLocId.get(loc.id) ?? [] as proposal}
			<button
				type="button"
				class="mt-0.5 flex w-full items-baseline gap-1 text-left text-xs text-muted-foreground hover:text-foreground"
				onmousedown={(e) => { e.preventDefault(); drafts[loc.id] = proposal.proposed_value; }}
			>
				<span class="shrink-0 text-muted-foreground/50">↳</span>
				<span class="break-words">{proposal.proposed_value}</span>
			</button>
		{/each}
	{/if}
{/snippet}

{#snippet translationCell(loc: LocalizationWithKey)}
	<Table.Cell class="whitespace-normal">
		{@render translationInput(loc)}
	</Table.Cell>
{/snippet}

<div class="p-4 md:p-6">
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
			onValueChange={(v) => { stateFilter = (v ?? '') as LocalizationState | ''; resetPagination(); }}
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

		<!-- Mobile cards -->
		<div class="space-y-3 md:hidden">
			{#each grouped as group}
				{#if group.entries.length === 1 && group.entries[0].variation_type === 'none'}
					{@const loc = group.entries[0]}
					<div class="rounded-lg border p-4 space-y-3">
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0 flex-1">
								<a href="/projects/{projectId}/strings/{loc.string_key_id}?language={language}" class="block break-all font-mono text-xs font-medium hover:underline">
									{loc.key}
								</a>
								{#if loc.source_value && loc.source_value !== loc.key}
									<p class="mt-0.5 break-words text-xs text-muted-foreground">
										<span class="font-medium">Source:</span> {loc.source_value}
									</p>
								{/if}
								{#if loc.comment}
									<p class="mt-1 break-words text-xs text-muted-foreground">
										<span class="font-medium">Comment:</span> {loc.comment}
									</p>
								{/if}
							</div>
							<span class="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium {stateColors[loc.state]}">{loc.state.replace('_', ' ')}</span>
						</div>
						{@render translationInput(loc, true)}
					</div>
				{:else}
					{@const anySource = group.entries.find(e => e.source_value && e.source_value !== group.key)?.source_value}
					<div class="rounded-lg border">
						<div class="border-b bg-muted/30 px-4 py-3">
							<a href="/projects/{projectId}/strings/{group.string_key_id}" class="block break-all font-mono text-xs font-medium hover:underline">
								{group.key}
							</a>
							{#if anySource}
								<p class="mt-0.5 break-words text-xs text-muted-foreground">
									<span class="font-medium">Source:</span> {anySource}
								</p>
							{/if}
							{#if group.entries[0].comment}
								<p class="mt-1 break-words text-xs text-muted-foreground">
									<span class="font-medium">Comment:</span> {group.entries[0].comment}
								</p>
							{/if}
						</div>
						{#each group.entries as loc}
							<div class="space-y-2 border-b px-4 py-3 last:border-b-0">
								<div class="flex items-center justify-between gap-2">
									<Badge variant="outline">{loc.variation_type}: {loc.variation_key}</Badge>
									<span class="rounded-full px-2 py-0.5 text-xs font-medium {stateColors[loc.state]}">{loc.state.replace('_', ' ')}</span>
								</div>
								{@render translationInput(loc, true)}
							</div>
						{/each}
					</div>
				{/if}
			{/each}
			{#if grouped.length === 0}
				<p class="py-12 text-center text-muted-foreground">No translations found.</p>
			{/if}
		</div>

		<!-- Desktop table -->
		<div class="hidden rounded-lg border md:block">
			<Table.Root class="table-fixed">
				<Table.Header>
					<Table.Row>
						<Table.Head class="w-56">Key</Table.Head>
						<Table.Head>Translation</Table.Head>
						<Table.Head class="w-48">Comment</Table.Head>
						<Table.Head class="w-32">State</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each grouped as group}
						{#if group.entries.length === 1 && group.entries[0].variation_type === 'none'}
							{@const loc = group.entries[0]}
							<Table.Row class="hover:bg-muted/50">
								<Table.Cell class="whitespace-normal">
									<a href="/projects/{projectId}/strings/{loc.string_key_id}?language={language}" class="block break-all font-mono text-xs font-medium hover:underline">
										{loc.key}
									</a>
									{#if loc.source_value && loc.source_value !== loc.key}
										<p class="mt-0.5 break-words text-xs text-muted-foreground">
											<span class="font-medium">Source:</span> {loc.source_value}
										</p>
									{/if}
								</Table.Cell>
								{@render translationCell(loc)}
								<Table.Cell class="whitespace-normal break-words text-sm text-muted-foreground">{loc.comment ?? '—'}</Table.Cell>
								<Table.Cell>
									<span class="rounded-full px-2 py-0.5 text-xs font-medium {stateColors[loc.state]}">{loc.state.replace('_', ' ')}</span>
								</Table.Cell>
							</Table.Row>
						{:else}
							<Table.Row class="bg-muted/30 hover:bg-muted/50">
								<Table.Cell class="whitespace-normal">
									<a href="/projects/{projectId}/strings/{group.string_key_id}" class="break-all font-mono text-xs font-medium hover:underline">
										{group.key}
									</a>
									{@const anySource = group.entries.find(e => e.source_value && e.source_value !== group.key)?.source_value}
									{#if anySource}
										<p class="mt-0.5 break-words text-xs text-muted-foreground">
											<span class="font-medium">Source:</span> {anySource}
										</p>
									{/if}
								</Table.Cell>
								<Table.Cell></Table.Cell>
								<Table.Cell class="whitespace-normal break-words text-sm text-muted-foreground">{group.entries[0].comment ?? '—'}</Table.Cell>
								<Table.Cell></Table.Cell>
							</Table.Row>
							{#each group.entries as loc}
								<Table.Row class="hover:bg-muted/50">
									<Table.Cell class="pl-8">
										<Badge variant="outline">{loc.variation_type}: {loc.variation_key}</Badge>
									</Table.Cell>
									{@render translationCell(loc)}
									<Table.Cell></Table.Cell>
									<Table.Cell>
										<span class="rounded-full px-2 py-0.5 text-xs font-medium {stateColors[loc.state]}">{loc.state.replace('_', ' ')}</span>
									</Table.Cell>
								</Table.Row>
							{/each}
						{/if}
					{/each}
					{#if grouped.length === 0}
						<Table.Row>
							<Table.Cell colspan={4} class="py-12 text-center text-muted-foreground">
								No translations found.
							</Table.Cell>
						</Table.Row>
					{/if}
				</Table.Body>
			</Table.Root>
		</div>

	{:else}

		<!-- Mobile cards -->
		<div class="space-y-2 md:hidden">
			{#each strings.data?.items ?? [] as str}
				{#if str.should_translate}
					<a href="/projects/{projectId}/strings/{str.id}" class="block rounded-lg border p-4 hover:bg-muted/50">
						<span class="block break-all font-mono text-xs font-medium">{str.key}</span>
						{#if str.comment}
							<p class="mt-1 break-words text-xs text-muted-foreground">{str.comment}</p>
						{/if}
						<p class="mt-1 text-xs text-muted-foreground">{new Date(str.updated_at).toLocaleDateString()}</p>
					</a>
				{:else}
					<div class="rounded-lg border p-4 opacity-50">
						<div class="flex flex-wrap items-center gap-2">
							<span class="break-all font-mono text-xs font-medium">{str.key}</span>
							<span class="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">do not translate</span>
						</div>
					</div>
				{/if}
			{/each}
			{#if (strings.data?.items.length ?? 0) === 0}
				<p class="py-12 text-center text-muted-foreground">No strings match your filters.</p>
			{/if}
		</div>

		<!-- Desktop table -->
		<div class="hidden rounded-lg border md:block">
			<Table.Root class="table-fixed">
				<Table.Header>
					<Table.Row>
						<Table.Head class="w-80">Key</Table.Head>
						<Table.Head>Comment</Table.Head>
						<Table.Head class="w-28">Updated</Table.Head>
					</Table.Row>
				</Table.Header>
				<Table.Body>
					{#each strings.data?.items ?? [] as str}
						<Table.Row class={str.should_translate ? 'cursor-pointer hover:bg-muted/50' : 'opacity-50'}>
							<Table.Cell class="whitespace-normal">
								{#if str.should_translate}
									<a href="/projects/{projectId}/strings/{str.id}" class="block break-all font-mono text-xs font-medium hover:underline">
										{str.key}
									</a>
								{:else}
									<div class="flex items-center gap-2">
										<span class="break-all font-mono text-xs font-medium">{str.key}</span>
										<span class="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">do not translate</span>
									</div>
								{/if}
							</Table.Cell>
							<Table.Cell class="whitespace-normal break-words text-sm text-muted-foreground">{str.comment ?? '—'}</Table.Cell>
							<Table.Cell class="text-xs text-muted-foreground">{new Date(str.updated_at).toLocaleDateString()}</Table.Cell>
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
			<Button variant="outline" size="sm" disabled={offset === 0} onclick={() => (offset = Math.max(0, offset - LIMIT))}>
				<ChevronLeft size={14} />
			</Button>
			<Button variant="outline" size="sm" disabled={!hasMore} onclick={() => (offset += LIMIT)}>
				<ChevronRight size={14} />
			</Button>
		</div>
	</div>
</div>
