type PrefillEntry = { running: boolean; message: string };

function createPrefillStore() {
	let state = $state<Record<string, PrefillEntry>>({});

	function storeKey(projectId: string, language: string) {
		return `${projectId}:${language}`;
	}

	// sessionStorage helpers (browser-only)
	const SESSION_KEY = 'prefill_pending';

	function getPending(): string[] {
		try {
			return JSON.parse(sessionStorage.getItem(SESSION_KEY) ?? '[]');
		} catch {
			return [];
		}
	}

	function addPending(projectId: string, language: string) {
		const k = storeKey(projectId, language);
		const pending = getPending();
		if (!pending.includes(k)) sessionStorage.setItem(SESSION_KEY, JSON.stringify([...pending, k]));
	}

	function removePending(projectId: string, language: string) {
		const k = storeKey(projectId, language);
		sessionStorage.setItem(SESSION_KEY, JSON.stringify(getPending().filter((p) => p !== k)));
	}

	return {
		get(projectId: string, language: string): PrefillEntry | undefined {
			return state[storeKey(projectId, language)];
		},

		set(projectId: string, language: string, entry: PrefillEntry) {
			state[storeKey(projectId, language)] = entry;
		},

		clear(projectId: string, language: string) {
			delete state[storeKey(projectId, language)];
		},

		/** Languages for this project that were still pending when the page last unloaded. */
		pendingLanguages(projectId: string): string[] {
			return getPending()
				.filter((k) => k.startsWith(`${projectId}:`))
				.map((k) => k.slice(projectId.length + 1));
		},

		async watch(
			projectId: string,
			language: string,
			baseUrl: string,
			accessToken: string | null,
			onReady: () => void
		) {
			// Skip if already watching
			if (state[storeKey(projectId, language)]?.running) return;

			addPending(projectId, language);
			this.set(projectId, language, {
				running: true,
				message: `Generating AI suggestions for ${language}…`
			});

			try {
				const res = await fetch(
					`${baseUrl}/api/projects/${projectId}/languages/${language}/prefill/stream`,
					{ headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {} }
				);
				if (!res.ok || !res.body) return;

				const reader = res.body.getReader();
				const decoder = new TextDecoder();
				let buffer = '';

				while (true) {
					const { done, value } = await reader.read();
					if (done) break;
					buffer += decoder.decode(value, { stream: true });
					const lines = buffer.split('\n');
					buffer = lines.pop() ?? '';
					for (const line of lines) {
						if (!line.startsWith('data:')) continue;
						const payload = JSON.parse(line.slice(5).trim());
						if (payload.status === 'ready' && payload.filled > 0) {
							this.set(projectId, language, {
								running: false,
								message: `${payload.filled} AI suggestion${payload.filled !== 1 ? 's' : ''} generated for ${language}.`
							});
							onReady();
						} else {
							this.clear(projectId, language);
						}
						return;
					}
				}
			} catch {
				// best-effort
			} finally {
				removePending(projectId, language);
				const entry = state[storeKey(projectId, language)];
				if (entry?.running) this.clear(projectId, language);
			}
		}
	};
}

export const prefillStore = createPrefillStore();
