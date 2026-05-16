<script lang="ts">
	import '../app.css';
	import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query';
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth.svelte';
	import { legalStore } from '$lib/stores/legal.svelte';
	import { onMount } from 'svelte';
	import { Toaster, toast } from 'svelte-sonner';

	let { children } = $props();

	function extractMessage(err: unknown): string {
		if (err && typeof err === 'object') {
			const detail = (err as Record<string, unknown>).detail;
			if (detail && typeof detail === 'object') {
				const msg = (detail as Record<string, unknown>).message;
				if (typeof msg === 'string') return msg;
			}
			if (typeof detail === 'string') return detail;
			const msg = (err as Record<string, unknown>).message;
			if (typeof msg === 'string') return msg;
		}
		return 'An unexpected error occurred.';
	}

	const queryClient = new QueryClient({
		defaultOptions: {
			queries: {
				staleTime: 30_000,
				retry: 1
			}
		}
	});

	queryClient.getQueryCache().subscribe((event) => {
		if (event?.type === 'updated' && event.query.state.status === 'error') {
			toast.error('Failed to load data', {
				description: extractMessage(event.query.state.error)
			});
		}
	});

	queryClient.getMutationCache().subscribe((event) => {
		if (event?.type === 'updated' && event.mutation?.state.status === 'error') {
			toast.error('Action failed', {
				description: extractMessage(event.mutation.state.error)
			});
		}
	});

	const COOKIE_KEY = 'lz_cookie_notice';
	let cookieNoticeDismissed = $state(true);

	onMount(() => {
		auth.init();
		legalStore.init();
		cookieNoticeDismissed = localStorage.getItem(COOKIE_KEY) === '1';
	});

	function dismissCookieNotice() {
		localStorage.setItem(COOKIE_KEY, '1');
		cookieNoticeDismissed = true;
	}
</script>

<QueryClientProvider client={queryClient}>
	<Toaster richColors closeButton position="top-right" />
	{@render children()}
	{@const hasSidebar = !$page.url.pathname.startsWith('/legal') && !$page.url.pathname.startsWith('/login') && !$page.url.pathname.startsWith('/register') && !$page.url.pathname.startsWith('/recover')}
	{#if !cookieNoticeDismissed && !(legalStore.hasPrivacy && $page.url.pathname === '/legal/privacy') && !(legalStore.hasImprint && $page.url.pathname === '/legal/imprint')}
		<div class="fixed bottom-16 left-4 right-4 z-50 rounded-xl border bg-card px-4 py-3 shadow-lg md:bottom-0 md:right-0 md:rounded-none md:border-t md:border-x-0 md:border-b-0 {hasSidebar ? 'md:left-56' : 'md:left-0'}">
			<div class="mx-auto flex max-w-3xl items-center gap-4">
				<p class="flex-1 text-sm text-muted-foreground">
					This site uses cookies and local storage for authentication.
					{#if legalStore.hasPrivacy}
						<a href="/legal/privacy" class="underline hover:text-foreground">Privacy policy</a>
					{/if}
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
