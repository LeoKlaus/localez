<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { legalStore } from '$lib/stores/legal.svelte';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	let { children } = $props();

	onMount(() => {
		if (auth.isAuthenticated) goto('/projects');
	});
</script>

<div class="flex min-h-svh flex-col items-center justify-center bg-background p-4">
	<div class="w-full max-w-sm">
		<div class="mb-8 text-center">
			<h1 class="text-2xl font-bold tracking-tight">Localez</h1>
			<p class="text-sm text-muted-foreground">Localization management</p>
		</div>
		{@render children()}
	</div>
	{#if legalStore.hasImprint || legalStore.hasPrivacy || legalStore.hasContributions}
		<footer class="mt-8 flex gap-4 text-xs text-muted-foreground">
			{#if legalStore.hasImprint}
				<a href="/legal/imprint" class="hover:text-foreground hover:underline">Imprint</a>
			{/if}
			{#if legalStore.hasPrivacy}
				<a href="/legal/privacy" class="hover:text-foreground hover:underline">Privacy</a>
			{/if}
			{#if legalStore.hasContributions}
				<a href="/legal/contributions" class="hover:text-foreground hover:underline">Contribution Guidelines</a>
			{/if}
		</footer>
	{/if}
</div>
