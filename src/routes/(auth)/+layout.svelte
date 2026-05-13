<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	let { children } = $props();

	onMount(() => {
		if (auth.isAuthenticated) goto('/projects');
	});
</script>

<div class="flex min-h-svh items-center justify-center bg-background p-4">
	<div class="w-full max-w-sm">
		<div class="mb-8 text-center">
			<h1 class="text-2xl font-bold tracking-tight">Localez</h1>
			<p class="text-sm text-muted-foreground">Localization management</p>
		</div>
		{@render children()}
	</div>
</div>
