import type { components } from '$lib/api/schema.d.ts';

type MeResponse = components['schemas']['MeResponse'];

const ACCESS_TOKEN_KEY = 'lz_access';
const REFRESH_TOKEN_KEY = 'lz_refresh';
const USER_KEY = 'lz_user';

function createAuth() {
	let accessToken = $state<string | null>(null);
	let user = $state<MeResponse | null>(null);

	function init() {
		if (typeof localStorage === 'undefined') return;
		const storedToken = localStorage.getItem(ACCESS_TOKEN_KEY);
		if (storedToken) accessToken = storedToken;
		const storedUser = localStorage.getItem(USER_KEY);
		if (storedUser) {
			try { user = JSON.parse(storedUser); } catch { /* ignore */ }
		}
	}

	function setTokens(access: string, refresh: string) {
		accessToken = access;
		localStorage.setItem(ACCESS_TOKEN_KEY, access);
		localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
	}

	function clear() {
		accessToken = null;
		user = null;
		localStorage.removeItem(ACCESS_TOKEN_KEY);
		localStorage.removeItem(REFRESH_TOKEN_KEY);
		localStorage.removeItem(USER_KEY);
	}

	return {
		get accessToken() { return accessToken; },
		get refreshToken() {
			if (typeof localStorage === 'undefined') return null;
			return localStorage.getItem(REFRESH_TOKEN_KEY);
		},
		get user() { return user; },
		set user(u: MeResponse | null) {
			user = u;
			if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
			else localStorage.removeItem(USER_KEY);
		},
		get isAuthenticated() { return !!accessToken; },
		get isAdmin() { return user?.global_role === 'admin'; },
		get totpEnabled() { return user?.totp_enabled ?? false; },
		get passkeysConfigured() { return user?.passkeys_configured ?? false; },
		init,
		setTokens,
		clear
	};
}

export const auth = createAuth();
