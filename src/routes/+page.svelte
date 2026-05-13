<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';

	onMount(() => {
		goto(auth.isAuthenticated ? '/projects' : '/login', { replaceState: true });
	});
</script>
