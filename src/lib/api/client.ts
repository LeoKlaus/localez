import createClient, { type Middleware } from 'openapi-fetch';
import type { paths } from './schema.d.ts';
import { auth } from '$lib/stores/auth.svelte';

const BASE_URL = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL ?? '');

const client = createClient<paths>({ baseUrl: BASE_URL });

let isRefreshing = false;
let refreshQueue: Array<(token: string | null) => void> = [];

function drainQueue(token: string | null) {
	refreshQueue.forEach((cb) => cb(token));
	refreshQueue = [];
}

const authMiddleware: Middleware = {
	async onRequest({ request }) {
		const token = auth.accessToken;
		if (token) {
			request.headers.set('Authorization', `Bearer ${token}`);
		}
		return request;
	},

	async onResponse({ response, request }) {
		if (response.status !== 401) return response;

		const refreshToken = auth.refreshToken;
		if (!refreshToken) {
			auth.clear();
			return response;
		}

		if (isRefreshing) {
			const newToken = await new Promise<string | null>((resolve) => {
				refreshQueue.push(resolve);
			});
			if (!newToken) return response;
			const retried = request.clone();
			retried.headers.set('Authorization', `Bearer ${newToken}`);
			return fetch(retried);
		}

		isRefreshing = true;
		try {
			const res = await fetch(`${BASE_URL}/auth/refresh`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ refresh_token: refreshToken })
			});

			if (!res.ok) {
				auth.clear();
				drainQueue(null);
				return response;
			}

			const data = await res.json();
			auth.setTokens(data.access_token, data.refresh_token);
			drainQueue(data.access_token);

			const retried = request.clone();
			retried.headers.set('Authorization', `Bearer ${data.access_token}`);
			return fetch(retried);
		} finally {
			isRefreshing = false;
		}
	}
};

client.use(authMiddleware);

export { client };
