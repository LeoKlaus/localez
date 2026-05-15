<script lang="ts">
	let { children } = $props();
</script>

<div class="min-h-svh bg-background">
	<header class="border-b">
		<div class="mx-auto flex h-14 max-w-3xl items-center gap-4 px-4">
			<a href="/" class="text-sm text-muted-foreground hover:text-foreground">← Back</a>
			<span class="font-bold tracking-tight">Localez</span>
		</div>
	</header>
	<main class="mx-auto max-w-3xl px-4 py-10">
		{@render children()}
	</main>
</div>
