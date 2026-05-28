import type { components } from '$lib/api/schema.d.ts';

type MeResponse = components['schemas']['MeResponse'];

const USER_KEY = 'lz_user';

function createAuth() {
	let accessToken = $state<string | null>(null);
	let user = $state<MeResponse | null>(null);
	let authReady = $state(false);

	// Eagerly restore cached user profile from localStorage (synchronous — safe
	// to do at module init time since we're in the browser by the time this runs).
	if (typeof localStorage !== 'undefined') {
		const stored = localStorage.getItem(USER_KEY);
		if (stored) {
			try {
				user = JSON.parse(stored) as MeResponse;
			} catch {
				localStorage.removeItem(USER_KEY);
			}
		}
	}

	/**
	 * Exchange the HttpOnly refresh-token cookie for a fresh access token.
	 * Returns true on success. Called once on app mount and by the auth
	 * middleware whenever a request gets a 401.
	 */
	async function tryRefresh(): Promise<boolean> {
		try {
			const res = await fetch('/api/auth/refresh/cookie', { method: 'POST' });
			if (res.ok) {
				const data = await res.json();
				accessToken = data.access_token as string;
				return true;
			}
			// Cookie is gone / expired — clear stale user profile.
			user = null;
			if (typeof localStorage !== 'undefined') localStorage.removeItem(USER_KEY);
		} catch {
			// Network error — leave state unchanged so offline usage still works.
		}
		return false;
	}

	function setToken(access: string) {
		accessToken = access;
	}

	function setReady() {
		authReady = true;
	}

	function clear() {
		accessToken = null;
		user = null;
		if (typeof localStorage !== 'undefined') localStorage.removeItem(USER_KEY);
	}

	return {
		get accessToken() {
			return accessToken;
		},
		get user() {
			return user;
		},
		set user(u: MeResponse | null) {
			user = u;
			if (typeof localStorage !== 'undefined') {
				if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
				else localStorage.removeItem(USER_KEY);
			}
		},
		get isAuthenticated() {
			return !!accessToken;
		},
		get authReady() {
			return authReady;
		},
		get isAdmin() {
			return !!accessToken && user?.global_role === 'admin';
		},
		get totpEnabled() {
			return user?.totp_enabled ?? false;
		},
		get passkeysConfigured() {
			return user?.passkeys_configured ?? false;
		},
		setToken,
		setReady,
		clear,
		tryRefresh,
	};
}

export const auth = createAuth();
