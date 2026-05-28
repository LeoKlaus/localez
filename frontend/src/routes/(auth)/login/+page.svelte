<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { client } from '$lib/api/client';
	import { useQueryClient } from '@tanstack/svelte-query';
	import { startAuthentication } from '@simplewebauthn/browser';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Alert from '$lib/components/ui/alert';
	import { Separator } from '$lib/components/ui/separator';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');
	const qc = useQueryClient();

	let username = $state('');
	let password = $state('');
	let totpCode = $state('');
	let needsTotp = $state(false);
	let error = $state('');
	let loading = $state(false);

	async function fetchMe(token: string) {
		const res = await fetch(`${BASE_URL}/api/users/me`, {
			headers: { Authorization: `Bearer ${token}` }
		});
		if (res.ok) auth.user = await res.json();
	}

	async function handleLogin(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		loading = true;

		try {
			const res = await fetch(`${BASE_URL}/api/auth/login/cookie`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					username,
					password,
					totp_code: needsTotp && totpCode ? totpCode : undefined
				})
			});

			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				if (res.status === 401 && data.detail?.code === 'TOTP_REQUIRED') {
					needsTotp = true;
					error = '';
					return;
				}
				const detail = data.detail;
				error =
					(typeof detail === 'object' && detail !== null ? detail.message : detail) ??
					data.message ??
					'Login failed. Check your credentials.';
				return;
			}

			const data = await res.json();
			auth.setToken(data.access_token);
			await fetchMe(data.access_token);
			qc.clear();
			goto('/projects');
		} finally {
			loading = false;
		}
	}

	async function handlePasskey() {
		error = '';
		loading = true;

		try {
			const beginRes = await fetch(`${BASE_URL}/api/auth/passkey/authenticate/begin`, {
				method: 'POST'
			});
			if (!beginRes.ok) {
				error = 'Could not start passkey authentication.';
				return;
			}
			const { options, challenge_token } = await beginRes.json();
			const credential = await startAuthentication({ optionsJSON: options });

			const completeRes = await fetch(`${BASE_URL}/api/auth/passkey/authenticate/complete/cookie`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ credential, challenge_token })
			});

			if (!completeRes.ok) {
				error = 'Passkey authentication failed.';
				return;
			}

			const data = await completeRes.json();
			auth.setToken(data.access_token);
			await fetchMe(data.access_token);
			qc.clear();
			goto('/projects');
		} catch (err) {
			if (err instanceof Error && err.name !== 'NotAllowedError') {
				error = err.message;
			}
		} finally {
			loading = false;
		}
	}
</script>

<Card.Root>
	<Card.Header>
		<Card.Title>Sign in</Card.Title>
		<Card.Description>Enter your credentials to access your projects.</Card.Description>
	</Card.Header>
	<Card.Content class="space-y-4">
		{#if error}
			<Alert.Root variant="destructive">
				<Alert.Description>{error}</Alert.Description>
			</Alert.Root>
		{/if}

		<form onsubmit={handleLogin} class="space-y-4">
			<div class="space-y-2">
				<Label for="username">Username</Label>
				<Input id="username" bind:value={username} autocomplete="username" required />
			</div>
			<div class="space-y-2">
				<Label for="password">Password</Label>
				<Input
					id="password"
					type="password"
					bind:value={password}
					autocomplete="current-password"
					required
				/>
			</div>
			{#if needsTotp}
				<div class="space-y-2">
					<Label for="totp">Authenticator code</Label>
					<Input
						id="totp"
						bind:value={totpCode}
						inputmode="numeric"
						maxlength={6}
						placeholder="000000"
						autocomplete="one-time-code"
					/>
				</div>
			{/if}
			<Button type="submit" class="w-full" disabled={loading}>
				{loading ? 'Signing in…' : 'Sign in'}
			</Button>
		</form>

		<div class="flex items-center gap-3">
			<Separator class="flex-1" />
			<span class="text-xs text-muted-foreground">or</span>
			<Separator class="flex-1" />
		</div>

		<Button variant="outline" class="w-full" onclick={handlePasskey} disabled={loading}>
			Sign in with passkey
		</Button>
	</Card.Content>
	<Card.Footer class="flex-col gap-2 text-sm">
		<p>
			Don't have an account?
			<a href="/register" class="underline underline-offset-4">Register</a>
		</p>
		<p>
			<a href="/recover" class="text-muted-foreground underline underline-offset-4">
				Forgot password?
			</a>
		</p>
	</Card.Footer>
</Card.Root>
