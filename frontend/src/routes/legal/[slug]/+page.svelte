<script lang="ts">
	import { page } from '$app/stores';
	import { marked } from 'marked';

	let slug = $derived(($page.params as Record<string, string>).slug ?? '');

	let html = $state<string | null>(null);
	let notFound = $state(false);

	$effect(() => {
		html = null;
		notFound = false;
		fetch(`/legal/${slug}.md`)
			.then(async (res) => {
				if (!res.ok) { notFound = true; return; }
				const text = await res.text();
				html = await marked(text);
			})
			.catch(() => { notFound = true; });
	});
</script>

{#if notFound}
	<p class="text-muted-foreground">Page not found.</p>
{:else if html}
	<article class="prose prose-neutral max-w-none dark:prose-invert">
		{@html html}
	</article>
{:else}
	<div class="h-64 animate-pulse rounded-lg bg-muted"></div>
{/if}
