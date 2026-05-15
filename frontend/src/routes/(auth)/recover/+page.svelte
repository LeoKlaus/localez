<script lang="ts">
	import { goto } from '$app/navigation';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Alert from '$lib/components/ui/alert';
	import { Textarea } from '$lib/components/ui/textarea';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	let username = $state('');
	let recoveryWordsRaw = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let error = $state('');
	let success = $state(false);
	let loading = $state(false);

	async function handleRecover(e: SubmitEvent) {
		e.preventDefault();
		error = '';

		if (newPassword !== confirmPassword) {
			error = 'Passwords do not match.';
			return;
		}

		const recovery_words = recoveryWordsRaw
			.trim()
			.split(/\s+/)
			.filter((w) => w.length > 0);

		if (recovery_words.length !== 12) {
			error = 'Please enter exactly 12 recovery words.';
			return;
		}

		loading = true;
		try {
			const res = await fetch(`${BASE_URL}/api/auth/recover`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, recovery_words, new_password: newPassword })
			});

			if (!res.ok) {
				const data = await res.json().catch(() => ({}));
				error = data.detail ?? 'Recovery failed. Check your recovery words.';
				return;
			}

			success = true;
		} finally {
			loading = false;
		}
	}
</script>

<Card.Root>
	<Card.Header>
		<Card.Title>Recover account</Card.Title>
		<Card.Description>Enter your recovery words to reset your password.</Card.Description>
	</Card.Header>
	<Card.Content class="space-y-4">
		{#if error}
			<Alert.Root variant="destructive">
				<Alert.Description>{error}</Alert.Description>
			</Alert.Root>
		{/if}
		{#if success}
			<Alert.Root>
				<Alert.Description>
					Password reset successfully.
					<a href="/login" class="underline">Sign in</a>
				</Alert.Description>
			</Alert.Root>
		{:else}
			<form onsubmit={handleRecover} class="space-y-4">
				<div class="space-y-2">
					<Label for="username">Username</Label>
					<Input id="username" bind:value={username} required />
				</div>
				<div class="space-y-2">
					<Label for="words">Recovery words</Label>
					<Textarea
						id="words"
						bind:value={recoveryWordsRaw}
						placeholder="word1 word2 word3 … (12 words)"
						rows={3}
						required
					/>
					<p class="text-xs text-muted-foreground">Paste all 12 words separated by spaces.</p>
				</div>
				<div class="space-y-2">
					<Label for="newpass">New password</Label>
					<Input id="newpass" type="password" bind:value={newPassword} minlength={8} required />
				</div>
				<div class="space-y-2">
					<Label for="confirm">Confirm password</Label>
					<Input id="confirm" type="password" bind:value={confirmPassword} required />
				</div>
				<Button type="submit" class="w-full" disabled={loading}>
					{loading ? 'Recovering…' : 'Reset password'}
				</Button>
			</form>
		{/if}
	</Card.Content>
	<Card.Footer class="text-sm">
		<a href="/login" class="underline underline-offset-4">Back to sign in</a>
	</Card.Footer>
</Card.Root>
