<script lang="ts">
	import '../app.css';
	import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth.svelte';
	import { onMount } from 'svelte';

	let { children } = $props();

	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				staleTime: 30_000,
				retry: 1
			}
		}
	});

	const COOKIE_KEY = 'lz_cookie_notice';
	let cookieNoticeDismissed = $state(true);

	onMount(() => {
		auth.init();
		cookieNoticeDismissed = localStorage.getItem(COOKIE_KEY) === '1';
	});

	function dismissCookieNotice() {
		localStorage.setItem(COOKIE_KEY, '1');
		cookieNoticeDismissed = true;
	}
</script>

<QueryClientProvider client={queryClient}>
	{@render children()}
	{@const hasSidebar = !$page.url.pathname.startsWith('/legal') && !$page.url.pathname.startsWith('/login') && !$page.url.pathname.startsWith('/register') && !$page.url.pathname.startsWith('/recover')}
	{#if !cookieNoticeDismissed && $page.url.pathname !== '/legal/privacy' && $page.url.pathname !== '/legal/imprint'}
		<div class="fixed bottom-16 left-4 right-4 z-50 rounded-xl border bg-card px-4 py-3 shadow-lg md:bottom-0 md:right-0 md:rounded-none md:border-t md:border-x-0 md:border-b-0 {hasSidebar ? 'md:left-56' : 'md:left-0'}">
			<div class="mx-auto flex max-w-3xl items-center gap-4">
				<p class="flex-1 text-sm text-muted-foreground">
					This site uses cookies and local storage for authentication.
					<a href="/legal/privacy" class="underline hover:text-foreground">Privacy policy</a>
				</p>
				<button
					onclick={dismissCookieNotice}
					class="shrink-0 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90"
				>
					Got it
				</button>
			</div>
		</div>
	{/if}
</QueryClientProvider>
