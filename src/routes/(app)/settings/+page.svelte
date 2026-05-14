<script lang="ts">
	import { auth } from '$lib/stores/auth.svelte';
	import { client } from '$lib/api/client';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => { if (!auth.isAuthenticated) goto('/login'); });
	import { startRegistration } from '@simplewebauthn/browser';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Alert from '$lib/components/ui/alert';
	import * as Dialog from '$lib/components/ui/dialog';
	import QRCode from 'qrcode';

	const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

	async function refreshMe() {
		const res = await fetch(`${BASE_URL}/api/users/me`, {
			headers: { Authorization: `Bearer ${auth.accessToken}` }
		});
		if (res.ok) auth.user = await res.json();
	}

	// ── Password change ──────────────────────────────────────────────────────
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let passwordError = $state('');
	let passwordSuccess = $state(false);
	let passwordLoading = $state(false);

	async function handlePasswordChange(e: SubmitEvent) {
		e.preventDefault();
		passwordError = '';
		passwordSuccess = false;

		if (newPassword !== confirmPassword) {
			passwordError = 'Passwords do not match.';
			return;
		}

		passwordLoading = true;
		try {
			const { error } = await client.PATCH('/api/users/me', {
				body: { current_password: currentPassword, new_password: newPassword }
			});
			if (error) {
				passwordError = 'Failed to change password. Check your current password.';
				return;
			}
			passwordSuccess = true;
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
		} finally {
			passwordLoading = false;
		}
	}

	// ── Passkey registration ────────────────────────────────────────────────
	let passkeyError = $state('');
	let passkeySuccess = $state(false);
	let passkeyLoading = $state(false);

	async function handlePasskeyRegister() {
		passkeyError = '';
		passkeySuccess = false;
		passkeyLoading = true;

		try {
			const beginRes = await fetch(`${BASE_URL}/api/auth/passkey/register/begin`, {
				method: 'POST',
				headers: { Authorization: `Bearer ${auth.accessToken}` }
			});
			if (!beginRes.ok) {
				passkeyError = 'Failed to start passkey registration.';
				return;
			}
			const { options, challenge_token } = await beginRes.json();
			const credential = await startRegistration({ optionsJSON: options });

			const completeRes = await fetch(`${BASE_URL}/api/auth/passkey/register/complete`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${auth.accessToken}`
				},
				body: JSON.stringify({ credential, challenge_token, name: 'My passkey' })
			});

			if (!completeRes.ok) {
				passkeyError = 'Passkey registration failed.';
				return;
			}
			passkeySuccess = true;
			await refreshMe();
		} catch (err) {
			if (err instanceof Error && err.name !== 'NotAllowedError') {
				passkeyError = err.message;
			}
		} finally {
			passkeyLoading = false;
		}
	}

	// ── TOTP setup ───────────────────────────────────────────────────────────
	let totpOpen = $state(false);
	let totpQrDataUrl = $state('');
	let totpSecret = $state('');
	let totpCode = $state('');
	let totpError = $state('');
	let totpLoading = $state(false);

	let totpDisableOpen = $state(false);
	let totpDisableCode = $state('');
	let totpDisableError = $state('');
	let totpDisableLoading = $state(false);

	async function beginTotpSetup() {
		totpError = '';
		totpCode = '';

		const res = await fetch(`${BASE_URL}/api/users/me/totp/setup`, {
			method: 'POST',
			headers: { Authorization: `Bearer ${auth.accessToken}` }
		});

		if (!res.ok) {
			totpError = 'Failed to start TOTP setup.';
			return;
		}

		const data = await res.json();
		totpSecret = data.secret ?? '';
		const uri = data.uri ?? '';
		if (uri) {
			totpQrDataUrl = await QRCode.toDataURL(uri, { width: 200, margin: 2 });
		}
		totpOpen = true;
	}

	async function verifyTotp(e: SubmitEvent) {
		e.preventDefault();
		totpError = '';
		totpLoading = true;

		try {
			const res = await fetch(`${BASE_URL}/api/users/me/totp/verify`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${auth.accessToken}`
				},
				body: JSON.stringify({ code: totpCode, secret: totpSecret })
			});

			if (!res.ok) {
				totpError = 'Invalid code. Try again.';
				return;
			}
			totpOpen = false;
			await refreshMe();
		} finally {
			totpLoading = false;
		}
	}

	async function disableTotp(e: SubmitEvent) {
		e.preventDefault();
		totpDisableError = '';
		totpDisableLoading = true;
		try {
			const res = await fetch(`${BASE_URL}/api/users/me/totp`, {
				method: 'DELETE',
				headers: {
					'Content-Type': 'application/json',
					Authorization: `Bearer ${auth.accessToken}`
				},
				body: JSON.stringify({ code: totpDisableCode })
			});
			if (!res.ok) {
				totpDisableError = 'Invalid code or failed to disable two-factor authentication.';
				return;
			}
			totpDisableOpen = false;
			totpDisableCode = '';
			await refreshMe();
		} finally {
			totpDisableLoading = false;
		}
	}
</script>

<div class="p-6">
	<h1 class="mb-6 text-2xl font-bold">Settings</h1>

	<div class="space-y-6 max-w-xl">
		<!-- Profile -->
		<Card.Root>
			<Card.Header>
				<Card.Title>Profile</Card.Title>
			</Card.Header>
			<Card.Content>
				<p class="text-sm">
					<span class="text-muted-foreground">Username:</span>
					<strong class="ml-2">{auth.user?.username ?? '…'}</strong>
				</p>
				<p class="mt-1 text-sm">
					<span class="text-muted-foreground">Role:</span>
					<strong class="ml-2">{auth.user?.global_role ?? '…'}</strong>
				</p>
			</Card.Content>
		</Card.Root>

		<!-- Password change -->
		<Card.Root>
			<Card.Header>
				<Card.Title>Change password</Card.Title>
			</Card.Header>
			<Card.Content>
				{#if passwordError}
					<Alert.Root variant="destructive" class="mb-4">
						<Alert.Description>{passwordError}</Alert.Description>
					</Alert.Root>
				{/if}
				{#if passwordSuccess}
					<Alert.Root class="mb-4">
						<Alert.Description>Password changed successfully.</Alert.Description>
					</Alert.Root>
				{/if}
				<form onsubmit={handlePasswordChange} class="space-y-4">
					<div class="space-y-2">
						<Label for="cur">Current password</Label>
						<Input
							id="cur"
							type="password"
							bind:value={currentPassword}
							autocomplete="current-password"
							required
						/>
					</div>
					<div class="space-y-2">
						<Label for="new">New password</Label>
						<Input
							id="new"
							type="password"
							bind:value={newPassword}
							autocomplete="new-password"
							minlength={8}
							required
						/>
					</div>
					<div class="space-y-2">
						<Label for="confirm">Confirm new password</Label>
						<Input
							id="confirm"
							type="password"
							bind:value={confirmPassword}
							autocomplete="new-password"
							required
						/>
					</div>
					<Button type="submit" disabled={passwordLoading}>
						{passwordLoading ? 'Saving…' : 'Change password'}
					</Button>
				</form>
			</Card.Content>
		</Card.Root>

		<!-- Passkeys -->
		<Card.Root>
			<Card.Header>
				<Card.Title>Passkeys</Card.Title>
				<Card.Description>
					Add a passkey to sign in without a password using Face ID, Touch ID, or a security key.
				</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-3">
				{#if passkeyError}
					<Alert.Root variant="destructive">
						<Alert.Description>{passkeyError}</Alert.Description>
					</Alert.Root>
				{/if}
				{#if passkeySuccess}
					<Alert.Root>
						<Alert.Description>Passkey registered successfully.</Alert.Description>
					</Alert.Root>
				{/if}
				<div class="flex items-center gap-3">
					{#if auth.passkeysConfigured}
						<span class="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
							Configured
						</span>
					{/if}
					<Button variant="outline" onclick={handlePasskeyRegister} disabled={passkeyLoading}>
						{passkeyLoading ? 'Registering…' : auth.passkeysConfigured ? 'Add another passkey' : 'Add passkey'}
					</Button>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- TOTP -->
		<Card.Root>
			<Card.Header>
				<Card.Title>Two-factor authentication</Card.Title>
				<Card.Description>
					Use an authenticator app (e.g. 1Password, Authy) for an extra layer of security.
				</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-3">
				{#if totpError && !totpOpen}
					<Alert.Root variant="destructive">
						<Alert.Description>{totpError}</Alert.Description>
					</Alert.Root>
				{/if}
				{#if auth.totpEnabled}
					<div class="flex items-center gap-3">
						<span class="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
							Enabled
						</span>
						<Button variant="outline" onclick={() => { totpDisableOpen = true; totpDisableCode = ''; totpDisableError = ''; }}>
							Disable
						</Button>
					</div>
				{:else}
					<Button variant="outline" onclick={beginTotpSetup}>Set up authenticator</Button>
				{/if}
			</Card.Content>
		</Card.Root>
	</div>
</div>

<!-- TOTP setup dialog -->
<Dialog.Root bind:open={totpOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Set up authenticator</Dialog.Title>
			<Dialog.Description>
				Scan the QR code with your authenticator app, then enter the 6-digit code to confirm.
			</Dialog.Description>
		</Dialog.Header>
		{#if totpQrDataUrl}
			<div class="flex justify-center">
				<img src={totpQrDataUrl} alt="TOTP QR code" class="rounded-md" width="200" height="200" />
			</div>
		{/if}
		{#if totpSecret}
			<div class="rounded-md bg-muted px-3 py-2 text-center font-mono text-sm">
				{totpSecret}
			</div>
			<p class="text-center text-xs text-muted-foreground">
				Can't scan? Enter this key manually.
			</p>
		{/if}
		<form onsubmit={verifyTotp} class="space-y-4">
			{#if totpError}
				<p class="text-sm text-destructive">{totpError}</p>
			{/if}
			<div class="space-y-2">
				<Label for="totpcode">Verification code</Label>
				<Input
					id="totpcode"
					bind:value={totpCode}
					inputmode="numeric"
					maxlength={6}
					placeholder="000000"
					autocomplete="one-time-code"
					required
				/>
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (totpOpen = false)}>Cancel</Button>
				<Button type="submit" disabled={totpLoading}>
					{totpLoading ? 'Verifying…' : 'Enable'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<!-- TOTP disable dialog -->
<Dialog.Root bind:open={totpDisableOpen}>
	<Dialog.Content class="sm:max-w-sm">
		<Dialog.Header>
			<Dialog.Title>Disable two-factor authentication</Dialog.Title>
			<Dialog.Description>
				Enter the current code from your authenticator app to confirm.
			</Dialog.Description>
		</Dialog.Header>
		<form onsubmit={disableTotp} class="space-y-4">
			{#if totpDisableError}
				<p class="text-sm text-destructive">{totpDisableError}</p>
			{/if}
			<div class="space-y-2">
				<Label for="disablecode">Authenticator code</Label>
				<Input
					id="disablecode"
					bind:value={totpDisableCode}
					inputmode="numeric"
					maxlength={6}
					placeholder="000000"
					autocomplete="one-time-code"
					required
				/>
			</div>
			<Dialog.Footer>
				<Button variant="outline" onclick={() => (totpDisableOpen = false)}>Cancel</Button>
				<Button type="submit" variant="destructive" disabled={totpDisableLoading}>
					{totpDisableLoading ? 'Disabling…' : 'Disable'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
