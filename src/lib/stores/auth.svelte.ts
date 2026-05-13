import type { components } from '$lib/api/schema.d.ts';

type User = components['schemas']['UserResponse'];

const ACCESS_TOKEN_KEY = 'lz_access';
const REFRESH_TOKEN_KEY = 'lz_refresh';

function createAuth() {
	let accessToken = $state<string | null>(null);
	let user = $state<User | null>(null);

	function init() {
		if (typeof localStorage === 'undefined') return;
		const stored = localStorage.getItem(ACCESS_TOKEN_KEY);
		if (stored) accessToken = stored;
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
	}

	return {
		get accessToken() {
			return accessToken;
		},
		get refreshToken() {
			if (typeof localStorage === 'undefined') return null;
			return localStorage.getItem(REFRESH_TOKEN_KEY);
		},
		get user() {
			return user;
		},
		set user(u: User | null) {
			user = u;
		},
		get isAuthenticated() {
			return !!accessToken;
		},
		get isAdmin() {
			return user?.global_role === 'admin';
		},
		init,
		setTokens,
		clear
	};
}

export const auth = createAuth();
