<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth.svelte';
	import { legalStore } from '$lib/stores/legal.svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Alert from '$lib/components/ui/alert';
	import * as Dialog from '$lib/components/ui/dialog';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	let username = $state('');
	let password = $state('');
	let confirmPassword = $state('');
	let error = $state('');
	let loading = $state(false);
	let privacyAccepted = $state(false);
	let contributionsAccepted = $state(false);
	let recoveryWords = $state<string[]>([]);
	let showRecovery = $state(false);

	async function handleRegister(e: SubmitEvent) {
		e.preventDefault();
		error = '';

		if (password !== confirmPassword) {
			error = 'Passwords do not match.';
			return;
		}

		loading = true;
		try {
			const res = await fetch(`${BASE_URL}/api/auth/register/cookie`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password })
			});

			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				error = data.detail ?? 'Registration failed.';
				return;
			}

			const data = await res.json();
			auth.setToken(data.access_token);
			recoveryWords = data.recovery_words;
			showRecovery = true;

			const meRes = await fetch(`${BASE_URL}/api/users/me`, {
				headers: { Authorization: `Bearer ${data.access_token}` }
			});
			if (meRes.ok) auth.user = await meRes.json();
		} finally {
			loading = false;
		}
	}

	function onRecoveryAcknowledged() {
		showRecovery = false;
		goto('/projects');
	}
</script>

<Card.Root>
	<Card.Header>
		<Card.Title>Create account</Card.Title>
		<Card.Description>Enter your details to get started.</Card.Description>
	</Card.Header>
	<Card.Content class="space-y-4">
		{#if error}
			<Alert.Root variant="destructive">
				<Alert.Description>{error}</Alert.Description>
			</Alert.Root>
		{/if}

		<form onsubmit={handleRegister} class="space-y-4">
			<div class="space-y-2">
				<Label for="username">Username</Label>
				<Input id="username" bind:value={username} minlength={3} maxlength={64} required />
			</div>
			<div class="space-y-2">
				<Label for="password">Password</Label>
				<Input id="password" type="password" bind:value={password} minlength={8} required />
			</div>
			<div class="space-y-2">
				<Label for="confirm">Confirm password</Label>
				<Input id="confirm" type="password" bind:value={confirmPassword} required />
			</div>
			<div class="flex items-center gap-2">
				<input
					id="privacy"
					type="checkbox"
					bind:checked={privacyAccepted}
					class="h-4 w-4 rounded border-input accent-primary"
					required
				/>
				<Label for="privacy" class="font-normal">
					I have read and agree to the
					<a href="/legal/privacy" target="_blank" class="underline underline-offset-4">privacy policy</a>
				</Label>
			</div>
			{#if legalStore.hasContributions}
				<div class="flex items-center gap-2">
					<input
						id="contributions"
						type="checkbox"
						bind:checked={contributionsAccepted}
						class="h-4 w-4 rounded border-input accent-primary"
						required
					/>
					<Label for="contributions" class="font-normal">
						I agree to the
						<a href="/legal/contributions" target="_blank" class="underline underline-offset-4">contribution guidelines</a>
					</Label>
				</div>
			{/if}
			<Button type="submit" class="w-full" disabled={loading || !privacyAccepted || (legalStore.hasContributions && !contributionsAccepted)}>
				{loading ? 'Creating account…' : 'Create account'}
			</Button>
		</form>
	</Card.Content>
	<Card.Footer class="text-sm">
		Already have an account?
		<a href="/login" class="ml-1 underline underline-offset-4">Sign in</a>
	</Card.Footer>
</Card.Root>

<Dialog.Root bind:open={showRecovery}>
	<Dialog.Content class="sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>Save your recovery words</Dialog.Title>
			<Dialog.Description>
				Store these 12 words somewhere safe. They are the only way to recover your account if you
				lose your password. They will not be shown again.
			</Dialog.Description>
		</Dialog.Header>
		<div class="grid grid-cols-3 gap-2 rounded-md border bg-muted p-4 font-mono text-sm">
			{#each recoveryWords as word, i}
				<div class="flex gap-1">
					<span class="text-muted-foreground">{i + 1}.</span>
					<span>{word}</span>
				</div>
			{/each}
		</div>
		<Dialog.Footer>
			<Button onclick={onRecoveryAcknowledged} class="w-full">
				I've saved my recovery words
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
